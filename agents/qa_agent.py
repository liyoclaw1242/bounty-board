"""
qa_agent.py — QA review agent.
Polls open PRs from agent branches, reviews with Claude Code, approves or requests changes.

Usage:
    python3 agents/qa_agent.py
"""

import os
import sys
import time
import random
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.github_client import GitHubClient
from lib import logger as log_lib


AGENT_ID = "qa-1"
BASE_INTERVAL = 180   # 3 min
MAX_INTERVAL = 600


def _get_pr_diff(repo_dir: str, pr_number: int) -> str:
    """Fetch PR diff via gh CLI."""
    try:
        result = subprocess.run(
            ["gh", "pr", "diff", str(pr_number)],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout[:8000]  # cap to avoid huge diffs
    except Exception:
        return "(could not fetch diff)"


def _review_with_claude(issue_body: str, diff: str, pr_title: str) -> tuple[str, str]:
    """
    Ask Claude Code to review the diff against the issue spec.
    Returns (event, comment) where event is APPROVE or REQUEST_CHANGES.
    """
    prompt = f"""You are a senior code reviewer. Review this PR.

## PR Title
{pr_title}

## Issue Spec
{issue_body[:2000]}

## Diff
{diff}

## Your Task
Review the diff against the spec. Reply in this exact format:

VERDICT: APPROVE
or
VERDICT: REQUEST_CHANGES

COMMENT:
<your review comment, 2-5 sentences>

Be concise. Focus on: correctness, tests, obvious bugs, spec compliance.
"""
    try:
        result = subprocess.run(
            ["claude", "--permission-mode", "bypassPermissions", "--print", prompt],
            capture_output=True, text=True, timeout=120,
        )
        output = result.stdout.strip()

        event = "REQUEST_CHANGES"
        if "VERDICT: APPROVE" in output:
            event = "APPROVE"

        # Extract comment after "COMMENT:"
        comment = output
        if "COMMENT:" in output:
            comment = output.split("COMMENT:", 1)[1].strip()

        return event, comment
    except Exception as e:
        return "COMMENT", f"QA agent error: {e}"


def run_qa_loop(gh: GitHubClient, repo_dir: str, bot_username: str):
    interval = BASE_INTERVAL
    log_lib.log(AGENT_ID, "start")

    while True:
        try:
            prs = gh.get_prs(state="open", per_page=10)

            if prs:
                reviewed = 0
                for pr in prs:
                    # Only review agent-created PRs
                    if not pr["head"]["ref"].startswith("agent/"):
                        continue

                    # Skip if already reviewed by this bot
                    reviews = gh.get_pr_reviews(pr["number"])
                    already_reviewed = any(
                        r.get("user", {}).get("login") == bot_username
                        for r in reviews
                    )
                    if already_reviewed:
                        continue

                    # Get issue number from branch name (agent/be-1/issue-42 → 42)
                    try:
                        issue_number = int(pr["head"]["ref"].split("/issue-")[1])
                        issue = gh.get_issue(issue_number)
                        issue_body = issue.get("body", "") or ""
                    except Exception:
                        issue_body = ""

                    diff = _get_pr_diff(repo_dir, pr["number"])
                    event, comment = _review_with_claude(issue_body, diff, pr["title"])

                    gh.submit_pr_review(pr["number"], event=event, body=comment)
                    log_lib.log(AGENT_ID, "review",
                                pr=pr["number"], verdict=event)
                    reviewed += 1

                if reviewed > 0:
                    interval = BASE_INTERVAL
                else:
                    interval = min(interval * 1.3, MAX_INTERVAL)
            else:
                interval = min(interval * 1.3, MAX_INTERVAL)

        except KeyboardInterrupt:
            print(f"\n[{AGENT_ID}] Interrupted.")
            log_lib.log(AGENT_ID, "stop", reason="keyboard_interrupt")
            break
        except Exception as e:
            log_lib.log(AGENT_ID, "error", event_detail="loop_error", exc=str(e))

        jitter = random.uniform(0, 20)
        print(f"[{AGENT_ID}] Sleeping {interval + jitter:.0f}s...")
        time.sleep(interval + jitter)


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
    repo_dir = os.path.expanduser(os.environ["BOUNTY_REPO_DIR"])
    bot_username = os.environ.get("GITHUB_BOT_USERNAME", "")

    run_qa_loop(gh=gh, repo_dir=repo_dir, bot_username=bot_username)
