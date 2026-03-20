"""QA Worker — Reviews PRs opened by execution agents."""

import os
import re
import sys
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.workers.base_worker import BaseWorker
from lib import logger as log_lib


class QAWorker(BaseWorker):
    BASE_INTERVAL = 180   # 3 min
    MAX_INTERVAL = 600

    def __init__(self, agent_id: str, repo_slug: str, app_state):
        super().__init__(
            agent_id=agent_id,
            agent_type="qa",
            agent_label="agent:qa",
            repo_slug=repo_slug,
            app_state=app_state,
        )
        repo = self.app_state.db.get_repo(repo_slug)
        self.bot_username = repo.get("bot_username", "") if repo else ""

    def poll_and_claim(self) -> dict | None:
        """Override: QA polls PRs, not issues."""
        try:
            prs = self.gh.get_prs(state="open")
        except Exception as e:
            log_lib.log(self.agent_id, "error", event_detail="poll_prs_failed", exc=str(e))
            return None

        if prs is None:
            return None

        for pr in prs:
            head = pr.get("head", {}).get("ref", "")
            if not head.startswith("agent/"):
                continue

            if self.bot_username:
                reviews = self.gh.get_pr_reviews(pr["number"])
                already_reviewed = any(
                    r.get("user", {}).get("login") == self.bot_username
                    for r in (reviews or [])
                )
                if already_reviewed:
                    continue

            return pr

        log_lib.log(self.agent_id, "poll", result="no_prs_to_review")
        return None

    def do_work(self, pr: dict) -> None:
        pr_number = pr["number"]
        head = pr.get("head", {}).get("ref", "")

        # Extract issue number from branch name
        m = re.search(r"issue-(\d+)", head)
        issue_number = int(m.group(1)) if m else None

        try:
            # Get issue body for context
            issue_body = ""
            if issue_number:
                issue = self.gh.get_issue(issue_number)
                if issue:
                    issue_body = issue.get("body", "") or ""

            # Get PR diff
            files = self.gh.get_pr_files(pr_number)
            diff_summary = ""
            if files:
                for f in files[:20]:
                    diff_summary += f"\n### {f['filename']} (+{f.get('additions', 0)} -{f.get('deletions', 0)})\n"
                    patch = f.get("patch", "")
                    if patch:
                        diff_summary += patch[:2000] + "\n"

            # Ask Claude to review
            prompt = f"""Review this PR for quality, correctness, and adherence to the spec.

## Issue Spec
{issue_body[:3000]}

## PR Diff
{diff_summary[:8000]}

Respond with EXACTLY one of:
- APPROVE: <2-5 sentence explanation>
- REQUEST_CHANGES: <2-5 sentence explanation>
"""
            result = subprocess.run(
                ["claude", "--print", prompt],
                capture_output=True, text=True, timeout=300,
            )

            verdict_text = result.stdout.strip() if result.returncode == 0 else ""

            if verdict_text.startswith("APPROVE"):
                event = "APPROVE"
                body = verdict_text
            else:
                event = "REQUEST_CHANGES"
                body = verdict_text or "Unable to determine verdict."

            self.gh.submit_pr_review(pr_number, event=event, body=body)
            log_lib.log(self.agent_id, "review",
                        pr=pr_number, verdict=event, issue=issue_number)

        except Exception as e:
            log_lib.log(self.agent_id, "error",
                        event_detail="qa_review", pr=pr_number, exc=str(e))
