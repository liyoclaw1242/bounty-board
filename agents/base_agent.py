"""
base_agent.py — Shared polling loop, claim logic, and Claude Code delegation.
All execution agents (BE, FE, DevOps) inherit from BaseAgent.
"""

import os
import time
import random
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.claims import init_db, try_claim, release_claim, renew_claim, update_claim_branch
from lib.github_client import GitHubClient
from lib import logger as log_lib
from lib import git_ops


class BaseAgent:
    BASE_INTERVAL = 120   # 2 min
    MAX_INTERVAL = 600    # 10 min (idle backoff)
    CLAUDE_TIMEOUT = 1800 # 30 min max per task

    def __init__(
        self,
        agent_id: str,
        agent_label: str,
        repo_dir: str,
        db_path: str,
        gh: GitHubClient,
    ):
        self.agent_id = agent_id
        self.agent_label = agent_label
        self.repo_dir = repo_dir
        self.db_path = db_path
        self.gh = gh
        self._interval = self.BASE_INTERVAL

        init_db(db_path)

    def poll_and_claim(self) -> dict | None:
        """
        Poll GitHub for a ready task matching our agent label.
        Try to claim the first available one via SQLite mutex.
        Returns the issue dict if claimed, None otherwise.
        """
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
            # 304 — nothing changed
            log_lib.log(self.agent_id, "poll", result="304_no_change")
            return None

        for issue in issues:
            if try_claim(self.db_path, issue["number"], self.agent_id):
                log_lib.log(self.agent_id, "claim",
                            issue=issue["number"], title=issue["title"])
                return issue
            else:
                log_lib.log(self.agent_id, "claim_fail",
                            issue=issue["number"], reason="already_claimed")

        log_lib.log(self.agent_id, "poll", result="no_tasks")
        return None

    def do_work(self, issue: dict) -> None:
        """
        Override in subclasses. Called with a claimed issue.
        Must release the claim when done (success or failure).
        """
        raise NotImplementedError

    def _run_claude_code(self, issue: dict) -> bool:
        """
        Delegate implementation to Claude Code via subprocess.
        Returns True on success, False on failure/timeout.
        """
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
        """Build the Claude Code prompt from an issue. Override to customize."""
        return f"""/bounty-agent

## Issue #{issue['number']}: {issue['title']}

{issue.get('body') or '(no description)'}

Commit when done: `git add -A && git commit -m "feat: {issue['title']} (closes #{issue['number']})"'`
"""

    def run(self) -> None:
        """Main polling loop. Runs forever until interrupted."""
        print(f"[{self.agent_id}] Starting. Polling for {self.agent_label} tasks...")
        log_lib.log(self.agent_id, "start", label=self.agent_label)

        while True:
            try:
                task = self.poll_and_claim()

                if task:
                    self.do_work(task)
                    self._interval = self.BASE_INTERVAL  # reset after work
                else:
                    # Back off when idle
                    self._interval = min(self._interval * 1.3, self.MAX_INTERVAL)

            except KeyboardInterrupt:
                print(f"\n[{self.agent_id}] Interrupted. Exiting.")
                log_lib.log(self.agent_id, "stop", reason="keyboard_interrupt")
                break
            except Exception as e:
                log_lib.log(self.agent_id, "error",
                            event_detail="loop_error", exc=str(e))
                # Never let an error kill the loop
                self._interval = self.BASE_INTERVAL

            jitter = random.uniform(0, 20)
            sleep_time = self._interval + jitter
            print(f"[{self.agent_id}] Sleeping {sleep_time:.0f}s...")
            time.sleep(sleep_time)
