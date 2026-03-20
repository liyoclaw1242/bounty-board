"""
AppState — singleton holding DB and GitHub clients.
Instantiated once in main.py lifespan, shared across all routers.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Database
from lib.github_client import GitHubClient


class AppState:
    def __init__(self, db: Database):
        self.db = db
        self.gh_clients: dict[str, GitHubClient] = {}

    def get_or_create_gh(self, repo_slug: str) -> GitHubClient:
        """Get cached GitHubClient, or create from DB."""
        if repo_slug not in self.gh_clients:
            repo = self.db.get_repo(repo_slug)
            if not repo:
                raise ValueError(f"Repo not found: {repo_slug}")
            self.gh_clients[repo_slug] = GitHubClient(
                token=repo["github_token"], repo=repo_slug
            )
        return self.gh_clients[repo_slug]

    def remove_gh(self, repo_slug: str) -> None:
        self.gh_clients.pop(repo_slug, None)
