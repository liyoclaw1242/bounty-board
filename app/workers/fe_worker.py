"""FE Worker — Frontend execution agent. Same workflow as BE with custom prompt."""

from app.workers.be_worker import BEWorker


class FEWorker(BEWorker):
    def __init__(self, agent_id: str, repo_slug: str, app_state):
        super().__init__(agent_id=agent_id, repo_slug=repo_slug, app_state=app_state)
        self.agent_type = "fe"
        self.agent_label = "agent:fe"
        self.name = f"worker-{agent_id}"

    def _build_prompt(self, issue: dict) -> str:
        return f"""/bounty-agent

## Issue #{issue['number']}: {issue['title']}

{issue.get('body') or '(no description)'}

### Frontend Guidelines
- Use React/TypeScript patterns consistent with the existing codebase
- Ensure accessibility (aria labels, keyboard navigation)
- Follow existing component patterns and styling conventions
- Write unit tests for new components

Commit when done: `git add -A && git commit -m "feat: {issue['title']} (closes #{issue['number']})"`
"""
