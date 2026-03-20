"""
Thread-safe SQLite database wrapper for the bounty board.
Single writer via threading.Lock — safe for use from FastAPI + worker threads.
"""

import os
import sqlite3
import threading
from typing import Optional


class Database:
    def __init__(self, db_path: str, schema_path: Optional[str] = None):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()

        # Init schema
        if schema_path and os.path.exists(schema_path):
            with open(schema_path) as f:
                self._conn.executescript(f.read())
        else:
            self._conn.executescript("""
                PRAGMA journal_mode = WAL;
                PRAGMA busy_timeout = 5000;
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS repos (
                    slug          TEXT PRIMARY KEY,
                    github_token  TEXT NOT NULL,
                    repo_dir      TEXT NOT NULL,
                    bot_username  TEXT DEFAULT '',
                    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS claims (
                    repo_slug    TEXT    NOT NULL,
                    issue_number INTEGER NOT NULL,
                    agent_id     TEXT    NOT NULL,
                    claimed_at   TEXT    NOT NULL DEFAULT (datetime('now')),
                    expires_at   TEXT    NOT NULL,
                    branch_name  TEXT,
                    pr_number    INTEGER,
                    PRIMARY KEY (repo_slug, issue_number),
                    FOREIGN KEY (repo_slug) REFERENCES repos(slug) ON DELETE CASCADE
                );
            """)
        self._conn.commit()

    def close(self):
        self._conn.close()

    # ── Repos ─────────────────────────────────────────────────────────────────

    def add_repo(self, slug: str, github_token: str, repo_dir: str,
                 bot_username: str = "") -> dict:
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO repos (slug, github_token, repo_dir, bot_username)
                   VALUES (?, ?, ?, ?)""",
                (slug, github_token, repo_dir, bot_username),
            )
            self._conn.commit()
        return self.get_repo(slug)

    def get_repos(self) -> list[dict]:
        rows = self._conn.execute("SELECT * FROM repos ORDER BY created_at").fetchall()
        return [dict(r) for r in rows]

    def get_repo(self, slug: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM repos WHERE slug = ?", (slug,)
        ).fetchone()
        return dict(row) if row else None

    def remove_repo(self, slug: str) -> bool:
        with self._lock:
            cursor = self._conn.execute("DELETE FROM repos WHERE slug = ?", (slug,))
            self._conn.commit()
            return cursor.rowcount > 0

    # ── Claims ────────────────────────────────────────────────────────────────

    def try_claim(self, repo_slug: str, issue_number: int, agent_id: str,
                  ttl_hours: int = 2) -> bool:
        with self._lock:
            self._conn.execute(
                "DELETE FROM claims WHERE expires_at < datetime('now')"
            )
            cursor = self._conn.execute(
                """INSERT OR IGNORE INTO claims (repo_slug, issue_number, agent_id, expires_at)
                   VALUES (?, ?, ?, datetime('now', ? || ' hours'))""",
                (repo_slug, issue_number, agent_id, str(ttl_hours)),
            )
            self._conn.commit()
            return cursor.rowcount == 1

    def release_claim(self, repo_slug: str, issue_number: int,
                      agent_id: str) -> bool:
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM claims WHERE repo_slug = ? AND issue_number = ? AND agent_id = ?",
                (repo_slug, issue_number, agent_id),
            )
            self._conn.commit()
            return cursor.rowcount > 0

    def renew_claim(self, repo_slug: str, issue_number: int, agent_id: str,
                    ttl_hours: int = 2) -> bool:
        with self._lock:
            cursor = self._conn.execute(
                """UPDATE claims SET expires_at = datetime('now', ? || ' hours')
                   WHERE repo_slug = ? AND issue_number = ? AND agent_id = ?""",
                (str(ttl_hours), repo_slug, issue_number, agent_id),
            )
            self._conn.commit()
            return cursor.rowcount == 1

    def list_claims(self, repo_slug: Optional[str] = None) -> list[dict]:
        if repo_slug:
            rows = self._conn.execute(
                """SELECT *, CASE WHEN expires_at < datetime('now') THEN 1 ELSE 0 END as expired
                   FROM claims WHERE repo_slug = ? ORDER BY claimed_at DESC""",
                (repo_slug,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT *, CASE WHEN expires_at < datetime('now') THEN 1 ELSE 0 END as expired
                   FROM claims ORDER BY claimed_at DESC"""
            ).fetchall()
        return [dict(r) for r in rows]

    def get_claim(self, repo_slug: str, issue_number: int) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM claims WHERE repo_slug = ? AND issue_number = ?",
            (repo_slug, issue_number),
        ).fetchone()
        return dict(row) if row else None

    def update_claim_branch(self, repo_slug: str, issue_number: int,
                            branch_name: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE claims SET branch_name = ? WHERE repo_slug = ? AND issue_number = ?",
                (branch_name, repo_slug, issue_number),
            )
            self._conn.commit()

    def update_claim_pr(self, repo_slug: str, issue_number: int,
                        pr_number: int) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE claims SET pr_number = ? WHERE repo_slug = ? AND issue_number = ?",
                (pr_number, repo_slug, issue_number),
            )
            self._conn.commit()
