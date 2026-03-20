"""
BaseWorker — Agent polling loop as a stoppable daemon thread.
Refactored from agents/base_agent.py to work within the FastAPI server.
"""

import os
import sys
import threading
import random
import subprocess
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from lib import logger as log_lib


class BaseWorker(threading.Thread):
    BASE_INTERVAL = 120   # 2 min
    MAX_INTERVAL = 600    # 10 min (idle backoff)
    CLAUDE_TIMEOUT = 1800 # 30 min max per task

    def __init__(self, agent_id: str, agent_type: str, agent_label: str,
                 repo_slug: str, app_state):
        super().__init__(daemon=True, name=f"worker-{agent_id}")
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.agent_label = agent_label
        self.repo_slug = repo_slug
        self.app_state = app_state
        self._stop_event = threading.Event()
        self._interval = self.BASE_INTERVAL
        self.status = "running"
        self.started_at = datetime.now().isoformat()

    @property
    def repo_dir(self) -> str:
        repo = self.app_state.db.get_repo(self.repo_slug)
        return repo["repo_dir"] if repo else ""

    @property
    def gh(self):
        return self.app_state.get_or_create_gh(self.repo_slug)

    def stop(self):
        self._stop_event.set()
        self.status = "stopping"

    def poll_and_claim(self) -> dict | None:
        try:
            issues = self.gh.get_issues(
                labels=[self.agent_label, "status:ready"],
                state="open",
                per_page=5,
            )
        except Exception as e:
            log_lib.log(self.agent_id, "error", event_detail="poll_failed", exc=str(e))
            return None

        if issues is None:
            log_lib.log(self.agent_id, "poll", result="304_no_change")
            return None

        for issue in issues:
            if self.app_state.db.try_claim(self.repo_slug, issue["number"], self.agent_id):
                log_lib.log(self.agent_id, "claim",
                            issue=issue["number"], title=issue["title"])
                return issue
            else:
                log_lib.log(self.agent_id, "claim_fail",
                            issue=issue["number"], reason="already_claimed")

        log_lib.log(self.agent_id, "poll", result="no_tasks")
        return None

    def do_work(self, issue: dict) -> None:
        raise NotImplementedError

    def _run_claude_code(self, issue: dict) -> bool:
        prompt = self._build_prompt(issue)
        log_lib.log(self.agent_id, "work_start",
                    issue=issue["number"], title=issue["title"])
        try:
            result = subprocess.run(
                ["claude", "--permission-mode", "bypassPermissions", "--print", prompt],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                timeout=self.CLAUDE_TIMEOUT,
            )
            if result.returncode == 0:
                log_lib.log(self.agent_id, "work_done", issue=issue["number"])
                return True
            else:
                log_lib.log(self.agent_id, "work_fail",
                            issue=issue["number"], stderr=result.stderr[:500])
                return False
        except subprocess.TimeoutExpired:
            log_lib.log(self.agent_id, "work_fail",
                        issue=issue["number"], reason="timeout")
            return False
        except Exception as e:
            log_lib.log(self.agent_id, "work_fail",
                        issue=issue["number"], exc=str(e))
            return False

    def _build_prompt(self, issue: dict) -> str:
        return f"""/bounty-agent

## Issue #{issue['number']}: {issue['title']}

{issue.get('body') or '(no description)'}

Commit when done: `git add -A && git commit -m "feat: {issue['title']} (closes #{issue['number']})"`
"""

    def run(self):
        log_lib.log(self.agent_id, "start", label=self.agent_label, repo=self.repo_slug)

        while not self._stop_event.is_set():
            try:
                task = self.poll_and_claim()
                if task:
                    self.do_work(task)
                    self._interval = self.BASE_INTERVAL
                else:
                    self._interval = min(self._interval * 1.3, self.MAX_INTERVAL)
            except Exception as e:
                log_lib.log(self.agent_id, "error",
                            event_detail="loop_error", exc=str(e))
                self._interval = self.BASE_INTERVAL

            jitter = random.uniform(0, 20)
            self._stop_event.wait(timeout=self._interval + jitter)

        self.status = "stopped"
        log_lib.log(self.agent_id, "stop", reason="requested")
