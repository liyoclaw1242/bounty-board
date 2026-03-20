"""
git_ops.py — Git operations for bounty board agents.
"""

import subprocess
import os
from typing import Optional


def _run(cmd: list[str], cwd: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)


def ensure_clean(repo_dir: str) -> None:
    """
    Ensure the repo is on main with no dirty state.
    Resets hard if dirty — agents should never have uncommitted changes lingering.
    """
    result = _run(["git", "status", "--porcelain"], repo_dir)
    if result.stdout.strip():
        _run(["git", "checkout", "main"], repo_dir, check=False)
        _run(["git", "reset", "--hard", "origin/main"], repo_dir)
        _run(["git", "clean", "-fd"], repo_dir)


def create_branch(repo_dir: str, branch_name: str) -> None:
    """
    Fetch latest main and create a new branch from it.
    Always branches from origin/main to avoid stale base.
    """
    _run(["git", "fetch", "origin", "main"], repo_dir)
    _run(["git", "checkout", "-b", branch_name, "origin/main"], repo_dir)


def commit_and_push(repo_dir: str, branch_name: str, message: str) -> None:
    """Stage all changes, commit, and push to origin."""
    _run(["git", "add", "-A"], repo_dir)
    result = _run(["git", "diff", "--cached", "--quiet"], repo_dir, check=False)
    if result.returncode == 0:
        # Nothing to commit
        return
    _run(["git", "commit", "-m", message], repo_dir)
    _run(["git", "push", "origin", branch_name], repo_dir)


def check_existing_branch(repo_dir: str, issue_number: int) -> Optional[str]:
    """
    Check if a remote branch already exists for this issue.
    Returns branch name if found, None otherwise.
    Useful for idempotency — avoids duplicate work after a crash.
    """
    result = _run(
        ["git", "ls-remote", "--heads", "origin", f"agent/*/issue-{issue_number}"],
        repo_dir,
        check=False
    )
    if result.stdout.strip():
        # Extract branch name from "sha\trefs/heads/branch-name"
        line = result.stdout.strip().split("\n")[0]
        ref = line.split("\t")[1]  # refs/heads/agent/be-1/issue-42
        return ref.replace("refs/heads/", "")
    return None


def branch_exists_remote(repo_dir: str, branch: str) -> bool:
    """Check if a specific branch exists on origin."""
    result = _run(
        ["git", "ls-remote", "--heads", "origin", branch],
        repo_dir,
        check=False
    )
    return bool(result.stdout.strip())


def cleanup_branch(repo_dir: str, branch_name: str) -> None:
    """
    Switch back to main and delete the local branch.
    Called on failure to leave the repo in a clean state.
    """
    _run(["git", "checkout", "main"], repo_dir, check=False)
    _run(["git", "branch", "-D", branch_name], repo_dir, check=False)
