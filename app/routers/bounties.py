"""Bounties router — create, list, and update bounty tasks (GitHub issues)."""

from fastapi import APIRouter, HTTPException, Request

from app.models import BountyCreate, BountyUpdate

router = APIRouter()


def _get_state(request: Request):
    return request.app.state.app_state


@router.post("", status_code=201)
def create_bounty(body: BountyCreate, request: Request):
    state = _get_state(request)
    repo = state.db.get_repo(body.repo_slug)
    if not repo:
        raise HTTPException(404, f"Repo not registered: {body.repo_slug}")

    gh = state.get_or_create_gh(body.repo_slug)

    # Build issue body
    issue_body = body.body
    if body.deps:
        dep_str = ", ".join(str(d) for d in body.deps)
        issue_body += f"\n\n<!-- deps: {dep_str} -->"

    labels = [f"agent:{body.agent_type}"]
    labels.append("status:blocked" if body.deps else "status:ready")

    issue = gh.create_issue(
        title=body.title,
        body=issue_body,
        labels=labels,
    )
    return issue


@router.get("")
def list_bounties(request: Request, repo_slug: str | None = None,
                  status: str | None = None, agent_type: str | None = None):
    state = _get_state(request)

    if not repo_slug:
        repos = state.db.get_repos()
    else:
        repo = state.db.get_repo(repo_slug)
        if not repo:
            raise HTTPException(404, f"Repo not registered: {repo_slug}")
        repos = [repo]

    all_issues = []
    for repo in repos:
        gh = state.get_or_create_gh(repo["slug"])
        labels = []
        if status:
            labels.append(f"status:{status}")
        if agent_type:
            labels.append(f"agent:{agent_type}")

        issues = gh.get_issues(labels=labels, state="open", per_page=50)
        if issues:
            for issue in issues:
                issue["_repo"] = repo["slug"]
            all_issues.extend(issues)

    return all_issues


@router.get("/{repo_slug:path}/issues/{number}")
def get_bounty(repo_slug: str, number: int, request: Request):
    state = _get_state(request)
    repo = state.db.get_repo(repo_slug)
    if not repo:
        raise HTTPException(404, f"Repo not registered: {repo_slug}")

    gh = state.get_or_create_gh(repo_slug)
    issue = gh.get_issue(number)
    if not issue:
        raise HTTPException(404, f"Issue #{number} not found")
    return issue


@router.patch("/{repo_slug:path}/issues/{number}")
def update_bounty(repo_slug: str, number: int, body: BountyUpdate,
                  request: Request):
    state = _get_state(request)
    repo = state.db.get_repo(repo_slug)
    if not repo:
        raise HTTPException(404, f"Repo not registered: {repo_slug}")

    gh = state.get_or_create_gh(repo_slug)

    if body.status:
        gh.replace_status_label(number, body.status)

    issue = gh.get_issue(number)
    return issue
