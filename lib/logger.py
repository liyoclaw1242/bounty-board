"""
logger.py — Structured JSONL logger for bounty board agents.
Query with: jq 'select(.event == "claim")' ~/.bounty/agent.log
"""

import json
import datetime
import os

LOG_PATH = os.path.expanduser(os.environ.get("BOUNTY_LOG", "~/.bounty/agent.log"))


def log(agent_id: str, event: str, **kwargs) -> None:
    """
    Append a structured log entry to the agent log.

    Events:
      poll          — polling cycle (found/not found)
      claim         — issue claimed
      claim_fail    — claim lost to another agent
      work_start    — beginning implementation
      work_done     — implementation complete
      work_fail     — implementation failed
      pr_opened     — PR created
      pr_fail       — PR creation failed
      review        — QA reviewed a PR
      unlock        — PM unlocked a blocked issue
      error         — unexpected error (include exc= for exception string)
    """
    entry = {
        "ts": datetime.datetime.now().isoformat(),
        "agent": agent_id,
        "event": event,
        **kwargs,
    }
    os.makedirs(os.path.dirname(os.path.abspath(LOG_PATH)), exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def tail(n: int = 20) -> list[dict]:
    """Return last N log entries."""
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH) as f:
        lines = f.readlines()
    return [json.loads(l) for l in lines[-n:] if l.strip()]
