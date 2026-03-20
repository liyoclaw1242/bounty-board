"""
claims.py — SQLite atomic claim mutex for bounty board agents.

SQLite is a MUTEX, not a state machine.
Row exists = someone is working on this issue. Row deleted = available.
GitHub Issues is the source of truth for task status.
"""

import sqlite3
import os
from typing import Optional

DEFAULT_DB = os.path.expanduser("~/.bounty/claims.db")


def init_db(db_path: str = DEFAULT_DB) -> None:
    """Initialize the claims database. Safe to call multiple times."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS claims (
            issue_number INTEGER PRIMARY KEY,
            agent_id     TEXT NOT NULL,
            claimed_at   TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at   TEXT NOT NULL,
            branch_name  TEXT,
            pr_number    INTEGER
        )
    """)
    conn.commit()
    conn.close()


def try_claim(db_path: str, issue_number: int, agent_id: str, ttl_hours: int = 2) -> bool:
    """
    Attempt to atomically claim an issue.

    Steps (in one transaction):
      1. DELETE expired claims (TTL passed)
      2. INSERT OR IGNORE — succeeds only if no active claim exists

    Returns True if this agent won the claim, False if already claimed.

    NOTE: Do NOT use INSERT OR REPLACE — it silently overwrites valid claims.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        with conn:
            conn.execute("DELETE FROM claims WHERE expires_at < datetime('now')")
            cursor = conn.execute(
                """INSERT OR IGNORE INTO claims (issue_number, agent_id, expires_at)
                   VALUES (?, ?, datetime('now', ? || ' hours'))""",
                (issue_number, agent_id, str(ttl_hours))
            )
            return cursor.rowcount == 1
    finally:
        conn.close()


def release_claim(db_path: str, issue_number: int, agent_id: str) -> None:
    """Release a claim after work is done or abandoned."""
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            conn.execute(
                "DELETE FROM claims WHERE issue_number = ? AND agent_id = ?",
                (issue_number, agent_id)
            )
    finally:
        conn.close()


def renew_claim(db_path: str, issue_number: int, agent_id: str, ttl_hours: int = 2) -> bool:
    """
    Heartbeat — extend claim TTL while still working.
    Call this periodically during long tasks to prevent expiry.
    Returns False if claim was lost (e.g. TTL expired and reaped by another agent).
    """
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            cursor = conn.execute(
                """UPDATE claims SET expires_at = datetime('now', ? || ' hours')
                   WHERE issue_number = ? AND agent_id = ?""",
                (str(ttl_hours), issue_number, agent_id)
            )
            return cursor.rowcount == 1
    finally:
        conn.close()


def list_claims(db_path: str = DEFAULT_DB) -> list[dict]:
    """Return all active claims. Useful for debugging."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT issue_number, agent_id, claimed_at, expires_at, branch_name, pr_number,
                   CASE WHEN expires_at < datetime('now') THEN 1 ELSE 0 END as expired
            FROM claims
            ORDER BY claimed_at DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_claim(db_path: str, issue_number: int) -> Optional[dict]:
    """Get a specific claim by issue number."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM claims WHERE issue_number = ?", (issue_number,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_claim_branch(db_path: str, issue_number: int, branch_name: str) -> None:
    """Record the branch name after creating it."""
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            conn.execute(
                "UPDATE claims SET branch_name = ? WHERE issue_number = ?",
                (branch_name, issue_number)
            )
    finally:
        conn.close()


def update_claim_pr(db_path: str, issue_number: int, pr_number: int) -> None:
    """Record the PR number after opening it."""
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            conn.execute(
                "UPDATE claims SET pr_number = ? WHERE issue_number = ?",
                (pr_number, issue_number)
            )
    finally:
        conn.close()


# ── CLI entrypoint (used by /create-agent-employ command) ───────────────────

if __name__ == "__main__":
    import sys

    db = os.path.expanduser(os.environ.get("BOUNTY_DB", "~/.bounty/claims.db"))
    init_db(db)

    if len(sys.argv) < 2:
        print("Usage: python3 claims.py <claim|release|status> [issue_number] [agent_id]")
        sys.exit(1)

    action = sys.argv[1]

    if action in ("claim", "release") and len(sys.argv) < 4:
        print(f"Usage: python3 claims.py {action} <issue_number> <agent_id>")
        sys.exit(1)

    if action == "claim":
        issue_num = int(sys.argv[2])
        agent_id = sys.argv[3]
        result = try_claim(db, issue_num, agent_id)
        print("1" if result else "0")
        sys.exit(0 if result else 1)

    elif action == "release":
        issue_num = int(sys.argv[2])
        agent_id = sys.argv[3]
        release_claim(db, issue_num, agent_id)
        print("released")

    elif action == "status":
        rows = list_claims(db)
        if not rows:
            print("No active claims.")
        else:
            print(f"{'ISSUE':>6}  {'AGENT':<30}  {'EXPIRES':>19}  {'STATE'}")
            print("-" * 72)
            for r in rows:
                state = "⚠️  EXPIRED" if r["expired"] else "✓ active"
                print(f"{r['issue_number']:>6}  {r['agent_id']:<30}  {r['expires_at']:>19}  {state}")
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)
