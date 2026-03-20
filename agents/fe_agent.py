"""
fe_agent.py — Frontend execution agent.
Identical flow to BE agent, but targets agent:fe issues.

Usage:
    python3 agents/fe_agent.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.be_agent import BEAgent, _load_env
from lib.github_client import GitHubClient


class FEAgent(BEAgent):
    def __init__(self, gh: GitHubClient, repo_dir: str, db_path: str, agent_id: str = "fe-1"):
        # Re-use all of BEAgent's do_work logic, just change label + id
        super().__init__(gh=gh, repo_dir=repo_dir, db_path=db_path, agent_id=agent_id)
        self.agent_label = "agent:fe"

    def _build_prompt(self, issue: dict) -> str:
        return f"""You are a Frontend engineer (React/TypeScript).
Implement the following GitHub issue exactly as described.

## Issue #{issue['number']}: {issue['title']}

{issue.get('body') or '(no description)'}

## Requirements
- Follow existing component patterns and styling conventions
- Use TypeScript with proper types
- Write component tests if applicable
- Ensure accessibility (aria labels, keyboard nav)
- Commit: "feat: {issue['title']} (closes #{issue['number']})"

Do not open a PR — the agent will handle that.
"""


if __name__ == "__main__":
    _load_env()

    token = os.environ["GITHUB_TOKEN"]
    repo = os.environ["BOUNTY_REPO"]
    repo_dir = os.path.expanduser(os.environ["BOUNTY_REPO_DIR"])
    db_path = os.path.expanduser(os.environ.get("BOUNTY_DB", "~/.bounty/claims.db"))
    agent_id = os.environ.get("AGENT_ID", "fe-1")

    gh = GitHubClient(token=token, repo=repo)
    agent = FEAgent(gh=gh, repo_dir=repo_dir, db_path=db_path, agent_id=agent_id)
    agent.run()
