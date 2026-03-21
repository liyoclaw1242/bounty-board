"""Repos router — register, list, and remove target repos."""

import os
import subprocess

from fastapi import APIRouter, HTTPException, Request, BackgroundTasks

from app.models import RepoCreate, RepoOut

router = APIRouter()


def _get_state(request: Request):
    return request.app.state.app_state


def _init_repo(slug: str, token: str, repo_dir: str):
    """Background task: clone repo + create labels."""
    os.makedirs(repo_dir, exist_ok=True)

    if not os.path.exists(os.path.join(repo_dir, ".git")):
        env = os.environ.copy()
        env["GH_TOKEN"] = token
        result = subprocess.run(
            ["gh", "repo", "clone", slug, repo_dir],
            env=env, capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"[init_repo] clone failed for {slug}: {result.stderr.strip()}")
            return

    # Create labels
    env = os.environ.copy()
    env["GH_TOKEN"] = token
    for agent in ["be", "fe", "qa", "devops", "arch", "design", "debug", "pm"]:
        subprocess.run(
            ["gh", "label", "create", f"agent:{agent}",
             "--repo", slug, "--color", "0E8A16",
             "--description", f"Tasks for {agent} agent", "--force"],
            env=env, capture_output=True, text=True,
        )
    for label, color, desc in [
        ("status:ready",       "0075CA", "Ready to be claimed"),
        ("status:blocked",     "E4E669", "Waiting on dependencies"),
        ("status:in-progress", "D93F0B", "Agent is working"),
        ("status:review",      "5319E7", "PR open, awaiting QA"),
    ]:
        subprocess.run(
            ["gh", "label", "create", label,
             "--repo", slug, "--color", color,
             "--description", desc, "--force"],
            env=env, capture_output=True, text=True,
        )


@router.post("", response_model=RepoOut, status_code=201)
def register_repo(body: RepoCreate, request: Request,
                  background_tasks: BackgroundTasks):
    state = _get_state(request)
    from app.config import settings

    repo_dir = body.repo_dir or os.path.join(
        settings.repos_base_dir, body.slug.replace("/", "/")
    )

    state.db.add_repo(body.slug, body.github_token, repo_dir,
                      body.bot_username, body.local_dir)
    background_tasks.add_task(_init_repo, body.slug, body.github_token, repo_dir)

    repo = state.db.get_repo(body.slug)
    return RepoOut(
        slug=repo["slug"],
        repo_dir=repo["repo_dir"],
        local_dir=repo["local_dir"],
        bot_username=repo["bot_username"],
        created_at=repo["created_at"],
    )


@router.get("", response_model=list[RepoOut])
def list_repos(request: Request):
    state = _get_state(request)
    repos = state.db.get_repos()
    return [
        RepoOut(
            slug=r["slug"],
            repo_dir=r["repo_dir"],
            local_dir=r["local_dir"],
            bot_username=r["bot_username"],
            created_at=r["created_at"],
        )
        for r in repos
    ]


@router.delete("/{slug:path}", status_code=204)
def remove_repo(slug: str, request: Request):
    state = _get_state(request)
    state.remove_gh(slug)

    if not state.db.remove_repo(slug):
        raise HTTPException(404, f"Repo not found: {slug}")
