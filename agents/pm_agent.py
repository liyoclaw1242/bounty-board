"""
pm_agent.py — PM orchestration agent.
Polls blocked issues, checks dependency satisfaction, unlocks downstream tasks.
Also provides helpers for creating well-structured issues.

Usage:
    python3 agents/pm_agent.py
"""

import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.github_client import GitHubClient
from lib import logger as log_lib

AGENT_ID = "pm-1"
POLL_INTERVAL = 300  # 5 min — PM doesn't need to be fast


def parse_deps(body: str) -> list[int]:
    """
    Parse machine-readable dependency list from issue body.
    Format: <!-- deps: 10, 12 -->
    This HTML comment is invisible in rendered markdown.
    """
    match = re.search(r'<!-- deps: ([\d,\s]+) -->', body or '')
    if not match:
        return []
    return [int(x.strip()) for x in match.group(1).split(',') if x.strip()]


def has_cycle(new_issue_num: int, deps: list[int], issue_bodies: dict[int, str]) -> bool:
    """
    DFS cycle detection for dependency graph.
    issue_bodies: {issue_number: body_text}
    Returns True if adding deps to new_issue_num would create a cycle.
    """
    visited: set[int] = set()

    def dfs(n: int) -> bool:
        if n == new_issue_num:
            return True
        if n in visited:
            return False
        visited.add(n)
        for dep in parse_deps(issue_bodies.get(n, "")):
            if dfs(dep):
                return True
        return False

    return any(dfs(d) for d in deps)


class PMAgent:
    def __init__(self, gh: GitHubClient):
        self.gh = gh

    def check_and_unlock(self) -> int:
        """
        Scan all status:blocked issues. For each, check if all deps are closed.
        Unlocks (sets status:ready) if all dependencies are satisfied.
        Returns count of issues unlocked.
        """
        blocked = self.gh.get_issues(
            labels=["status:blocked"],
            state="open",
            per_page=100,
        )

        if not blocked:
            return 0

        unlocked = 0
        for issue in blocked:
            deps = parse_deps(issue.get("body", ""))

            if not deps:
                # Marked blocked but no deps listed — unlock it
                self.gh.replace_status_label(issue["number"], "ready")
                log_lib.log(AGENT_ID, "unlock",
                            issue=issue["number"], reason="no_deps_found")
                unlocked += 1
                continue

            # Check all deps are closed
            all_done = True
            for dep_num in deps:
                try:
                    dep = self.gh.get_issue(dep_num)
                    if dep.get("state") != "closed":
                        all_done = False
                        break
                except Exception:
                    all_done = False
                    break

            if all_done:
                self.gh.replace_status_label(issue["number"], "ready")
                log_lib.log(AGENT_ID, "unlock",
                            issue=issue["number"], deps=deps)
                unlocked += 1

        return unlocked

    def create_task(
        self,
        title: str,
        body: str,
        agent_type: str,  # "be", "fe", "qa", "devops"
        deps: list[int] = None,
        priority: str = None,
    ) -> dict:
        """
        Create a well-structured GitHub issue for an execution agent.
        Automatically sets status:ready (or status:blocked if deps provided).
        Injects <!-- deps: N, M --> comment for machine parsing.
        """
        labels = [f"agent:{agent_type}"]

        if deps:
            # Validate no cycles before creating
            # (simplified — for full validation, pass all_issue_bodies)
            labels.append("status:blocked")
            deps_comment = f"\n\n<!-- deps: {', '.join(str(d) for d in deps)} -->"
            body = body + deps_comment
        else:
            labels.append("status:ready")

        if priority:
            labels.append(f"priority:{priority}")

        issue = self.gh.create_issue(title=title, body=body, labels=labels)
        log_lib.log(AGENT_ID, "issue_created",
                    issue=issue["number"], agent=agent_type, deps=deps or [])
        return issue

    def run(self) -> None:
        """Main PM loop — checks for unlockable blocked issues every 5 min."""
        print(f"[{AGENT_ID}] PM agent starting. Polling every {POLL_INTERVAL}s...")
        log_lib.log(AGENT_ID, "start")

        while True:
            try:
                count = self.check_and_unlock()
                if count:
                    print(f"[{AGENT_ID}] Unlocked {count} issue(s).")
                else:
                    print(f"[{AGENT_ID}] No issues to unlock.")
            except KeyboardInterrupt:
                print(f"\n[{AGENT_ID}] Interrupted.")
                log_lib.log(AGENT_ID, "stop", reason="keyboard_interrupt")
                break
            except Exception as e:
                log_lib.log(AGENT_ID, "error", event_detail="loop_error", exc=str(e))

            time.sleep(POLL_INTERVAL)


def _load_env():
    env_file = os.path.expanduser("~/.bounty/.env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


if __name__ == "__main__":
    _load_env()

    gh = GitHubClient(
        token=os.environ["GITHUB_TOKEN"],
        repo=os.environ["BOUNTY_REPO"],
    )
    agent = PMAgent(gh=gh)
    agent.run()
