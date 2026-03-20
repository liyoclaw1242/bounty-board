"""
be_agent.py — Backend execution agent.
Polls for agent:be + status:ready issues, implements via Claude Code, opens PRs.

Usage:
    cp .env.example ~/.bounty/.env  # configure once
    python3 agents/be_agent.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.claims import release_claim, update_claim_branch, update_claim_pr
from lib.github_client import GitHubClient
from lib import git_ops
from lib import logger as log_lib
from agents.base_agent import BaseAgent


class BEAgent(BaseAgent):
    def __init__(self, gh: GitHubClient, repo_dir: str, db_path: str, agent_id: str = "be-1"):
        super().__init__(
            agent_id=agent_id,
            agent_label="agent:be",
            repo_dir=repo_dir,
            db_path=db_path,
            gh=gh,
        )

    def do_work(self, issue: dict) -> None:
        number = issue["number"]
        branch = f"agent/{self.agent_id}/issue-{number}"

        try:
            # 1. Idempotency — check if branch already exists (crash recovery)
            existing = git_ops.check_existing_branch(self.repo_dir, number)
            if existing:
                log_lib.log(self.agent_id, "work_start",
                            issue=number, note="resuming_existing_branch", branch=existing)
                branch = existing
            else:
                # 2. Ensure clean git state
                git_ops.ensure_clean(self.repo_dir)
                # 3. Create branch from origin/main
                git_ops.create_branch(self.repo_dir, branch)
                update_claim_branch(self.db_path, number, branch)

            # 4. Run Claude Code
            success = self._run_claude_code(issue)
            if not success:
                git_ops.cleanup_branch(self.repo_dir, branch)
                release_claim(self.db_path, number, self.agent_id)
                log_lib.log(self.agent_id, "work_fail", issue=number,
                            reason="claude_code_failed")
                return

            # 5. Push branch
            git_ops.commit_and_push(
                self.repo_dir, branch,
                f"feat: {issue['title']} (closes #{number})"
            )

            # 6. Open PR
            pr_body = (
                f"Closes #{number}\n\n"
                f"## Summary\n\nAutomated implementation by `{self.agent_id}`.\n\n"
                f"## Issue\n\n{issue.get('body', '').strip()[:500]}"
            )
            try:
                pr = self.gh.create_pr(
                    title=f"[{self.agent_id}] {issue['title']}",
                    body=pr_body,
                    head=branch,
                    base="main",
                )
                pr_number = pr.get("number")
                update_claim_pr(self.db_path, number, pr_number)
                log_lib.log(self.agent_id, "pr_opened",
                            issue=number, pr=pr_number, branch=branch)

                # 7. Update issue label → status:review
                self.gh.replace_status_label(number, "review")

            except Exception as e:
                log_lib.log(self.agent_id, "pr_fail",
                            issue=number, exc=str(e))
                git_ops.cleanup_branch(self.repo_dir, branch)

        except Exception as e:
            log_lib.log(self.agent_id, "error",
                        issue=number, event_detail="do_work", exc=str(e))
            git_ops.cleanup_branch(self.repo_dir, branch)
        finally:
            # Always release claim — whether success or failure
            release_claim(self.db_path, number, self.agent_id)


# ── Entrypoint ──────────────────────────────────────────────────────────────

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

    token = os.environ["GITHUB_TOKEN"]
    repo = os.environ["BOUNTY_REPO"]
    repo_dir = os.path.expanduser(os.environ["BOUNTY_REPO_DIR"])
    db_path = os.path.expanduser(os.environ.get("BOUNTY_DB", "~/.bounty/claims.db"))
    agent_id = os.environ.get("AGENT_ID", "be-1")

    gh = GitHubClient(token=token, repo=repo)
    agent = BEAgent(gh=gh, repo_dir=repo_dir, db_path=db_path, agent_id=agent_id)
    agent.run()
