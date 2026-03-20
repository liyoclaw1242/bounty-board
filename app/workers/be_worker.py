"""BE Worker — Backend execution agent as a worker thread."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.workers.base_worker import BaseWorker
from lib import git_ops
from lib import logger as log_lib


class BEWorker(BaseWorker):
    def __init__(self, agent_id: str, repo_slug: str, app_state):
        super().__init__(
            agent_id=agent_id,
            agent_type="be",
            agent_label="agent:be",
            repo_slug=repo_slug,
            app_state=app_state,
        )

    def do_work(self, issue: dict) -> None:
        number = issue["number"]
        branch = f"agent/{self.agent_id}/issue-{number}"
        db = self.app_state.db

        try:
            existing = git_ops.check_existing_branch(self.repo_dir, number)
            if existing:
                log_lib.log(self.agent_id, "work_start",
                            issue=number, note="resuming_existing_branch", branch=existing)
                branch = existing
            else:
                git_ops.ensure_clean(self.repo_dir)
                git_ops.create_branch(self.repo_dir, branch)
                db.update_claim_branch(self.repo_slug, number, branch)

            success = self._run_claude_code(issue)
            if not success:
                git_ops.cleanup_branch(self.repo_dir, branch)
                db.release_claim(self.repo_slug, number, self.agent_id)
                return

            git_ops.commit_and_push(
                self.repo_dir, branch,
                f"feat: {issue['title']} (closes #{number})"
            )

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
                db.update_claim_pr(self.repo_slug, number, pr_number)
                log_lib.log(self.agent_id, "pr_opened",
                            issue=number, pr=pr_number, branch=branch)
                self.gh.replace_status_label(number, "review")
            except Exception as e:
                log_lib.log(self.agent_id, "pr_fail", issue=number, exc=str(e))
                git_ops.cleanup_branch(self.repo_dir, branch)

        except Exception as e:
            log_lib.log(self.agent_id, "error",
                        issue=number, event_detail="do_work", exc=str(e))
            git_ops.cleanup_branch(self.repo_dir, branch)
        finally:
            db.release_claim(self.repo_slug, number, self.agent_id)
