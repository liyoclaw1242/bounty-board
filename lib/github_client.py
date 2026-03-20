"""
github_client.py — GitHub REST API wrapper with ETag caching and rate limit handling.
"""

import time
import requests
from typing import Optional


class GitHubClient:
    API_BASE = "https://api.github.com"

    def __init__(self, token: str, repo: str):
        """
        Args:
            token: Fine-grained PAT with Issues/PRs/Contents read+write on the target repo
            repo:  "owner/repo"
        """
        self.token = token
        self.repo = repo
        self._etags: dict[str, str] = {}  # path → ETag

    def _headers(self, extra: dict = None) -> dict:
        h = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if extra:
            h.update(extra)
        return h

    def _get(self, path: str, params: dict = None, use_etag: bool = True) -> Optional[list | dict]:
        """
        GET with ETag conditional request support.
        Returns None on 304 (no changes).
        Handles 429 and 403 rate limits automatically.
        """
        url = f"{self.API_BASE}/repos/{self.repo}{path}"
        headers = self._headers()

        if use_etag and path in self._etags:
            headers["If-None-Match"] = self._etags[path]

        while True:
            resp = requests.get(url, headers=headers, params=params, timeout=30)

            if resp.status_code == 304:
                return None  # No changes

            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 60))
                time.sleep(wait)
                continue

            if resp.status_code == 403 and "rate limit" in resp.text.lower():
                reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait = max(reset - time.time(), 10)
                time.sleep(wait)
                continue

            resp.raise_for_status()

            if use_etag and "ETag" in resp.headers:
                self._etags[path] = resp.headers["ETag"]

            return resp.json()

    def _mutate(self, method: str, path: str, json: dict = None) -> dict:
        """POST/PUT/PATCH/DELETE with rate limit handling."""
        url = f"{self.API_BASE}/repos/{self.repo}{path}"
        fn = getattr(requests, method.lower())

        while True:
            resp = fn(url, headers=self._headers(), json=json, timeout=30)

            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 60))
                time.sleep(wait)
                continue

            if resp.status_code == 403 and "rate limit" in resp.text.lower():
                reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait = max(reset - time.time(), 10)
                time.sleep(wait)
                continue

            if resp.status_code == 204:
                return {}

            resp.raise_for_status()
            return resp.json()

    # ── Issues ──────────────────────────────────────────────────────────

    def get_issues(self, labels: list[str], state: str = "open", per_page: int = 5) -> Optional[list[dict]]:
        """
        Fetch open issues matching ALL given labels (AND logic).
        Returns None if 304 (no changes since last poll).
        Filters out PRs (GitHub Issues API returns both).
        """
        result = self._get("/issues", params={
            "labels": ",".join(labels),
            "state": state,
            "sort": "created",
            "direction": "asc",
            "per_page": str(per_page),
        })
        if result is None:
            return None
        return [i for i in result if "pull_request" not in i]

    def get_issue(self, number: int) -> dict:
        """Fetch a single issue by number."""
        return self._get(f"/issues/{number}", use_etag=False)

    def set_labels(self, issue_number: int, labels: list[str]) -> dict:
        """Atomically replace ALL labels on an issue (PUT)."""
        return self._mutate("PUT", f"/issues/{issue_number}/labels", {"labels": labels})

    def add_labels(self, issue_number: int, labels: list[str]) -> dict:
        """Append labels to an issue (POST)."""
        return self._mutate("POST", f"/issues/{issue_number}/labels", {"labels": labels})

    def replace_status_label(self, issue_number: int, new_status: str) -> dict:
        """
        Replace status:X with status:new_status, preserving other labels.
        Fetches current labels first to build the new set.
        """
        issue = self.get_issue(issue_number)
        current = [l["name"] for l in issue.get("labels", []) if not l["name"].startswith("status:")]
        current.append(f"status:{new_status}")
        return self.set_labels(issue_number, current)

    def post_comment(self, issue_number: int, body: str) -> dict:
        """Post a comment on an issue or PR."""
        return self._mutate("POST", f"/issues/{issue_number}/comments", {"body": body})

    def create_issue(self, title: str, body: str, labels: list[str]) -> dict:
        """Create a new issue."""
        return self._mutate("POST", "/issues", {
            "title": title,
            "body": body,
            "labels": labels,
        })

    def close_issue(self, number: int) -> dict:
        """Close an issue."""
        return self._mutate("PATCH", f"/issues/{number}", {"state": "closed"})

    # ── Pull Requests ────────────────────────────────────────────────────

    def get_prs(self, state: str = "open", per_page: int = 10) -> Optional[list[dict]]:
        """Fetch PRs. Returns None on 304."""
        return self._get("/pulls", params={
            "state": state,
            "sort": "created",
            "direction": "asc",
            "per_page": str(per_page),
        })

    def create_pr(self, title: str, body: str, head: str, base: str = "main") -> dict:
        """Open a new pull request."""
        return self._mutate("POST", "/pulls", {
            "title": title,
            "body": body,
            "head": head,
            "base": base,
        })

    def get_pr_reviews(self, pr_number: int) -> list[dict]:
        """List all reviews on a PR."""
        return self._get(f"/pulls/{pr_number}/reviews", use_etag=False) or []

    def submit_pr_review(self, pr_number: int, event: str, body: str) -> dict:
        """
        Submit a PR review.
        event: "APPROVE" | "REQUEST_CHANGES" | "COMMENT"
        """
        return self._mutate("POST", f"/pulls/{pr_number}/reviews", {
            "event": event,
            "body": body,
        })

    def get_pr_files(self, pr_number: int) -> list[dict]:
        """List files changed in a PR."""
        return self._get(f"/pulls/{pr_number}/files", use_etag=False) or []

    # ── Utility ─────────────────────────────────────────────────────────

    def get_rate_limit(self) -> dict:
        """Check current rate limit status."""
        resp = requests.get(
            f"{self.API_BASE}/rate_limit",
            headers=self._headers(),
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()
