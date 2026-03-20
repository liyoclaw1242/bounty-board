"""PM Worker — Unlocks blocked issues when dependencies are resolved."""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.workers.base_worker import BaseWorker
from lib import logger as log_lib


class PMWorker(BaseWorker):
    BASE_INTERVAL = 300   # 5 min
    MAX_INTERVAL = 600

    def __init__(self, agent_id: str, repo_slug: str, app_state):
        super().__init__(
            agent_id=agent_id,
            agent_type="pm",
            agent_label="status:blocked",
            repo_slug=repo_slug,
            app_state=app_state,
        )

    def poll_and_claim(self) -> dict | None:
        """Override: PM checks all blocked issues, doesn't claim via mutex."""
        try:
            issues = self.gh.get_issues(
                labels=["status:blocked"],
                state="open",
                per_page=20,
            )
        except Exception as e:
            log_lib.log(self.agent_id, "error", event_detail="poll_blocked", exc=str(e))
            return None

        if not issues:
            return None

        for issue in issues:
            body = issue.get("body") or ""
            m = re.search(r"<!--\s*deps:\s*([\d\s,]+)\s*-->", body)
            if not m:
                continue

            dep_numbers = [int(d.strip()) for d in m.group(1).split(",") if d.strip()]
            all_closed = True
            for dep in dep_numbers:
                dep_issue = self.gh.get_issue(dep)
                if dep_issue and dep_issue.get("state") != "closed":
                    all_closed = False
                    break

            if all_closed:
                return issue

        return None

    def do_work(self, issue: dict) -> None:
        number = issue["number"]
        try:
            self.gh.replace_status_label(number, "ready")
            log_lib.log(self.agent_id, "unlock", issue=number, title=issue["title"])
        except Exception as e:
            log_lib.log(self.agent_id, "error",
                        event_detail="unlock_fail", issue=number, exc=str(e))
