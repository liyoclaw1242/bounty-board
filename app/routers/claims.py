"""Claims router — manage atomic task claims."""

from fastapi import APIRouter, HTTPException, Request

from app.models import ClaimCreate, ClaimOut

router = APIRouter()


def _get_state(request: Request):
    return request.app.state.app_state


@router.post("", response_model=ClaimOut, status_code=201)
def create_claim(body: ClaimCreate, request: Request):
    state = _get_state(request)

    success = state.db.try_claim(
        body.repo_slug, body.issue_number, body.agent_id, body.ttl_hours
    )
    if not success:
        raise HTTPException(409, f"Issue #{body.issue_number} already claimed")

    claim = state.db.get_claim(body.repo_slug, body.issue_number)
    return ClaimOut(
        repo_slug=claim["repo_slug"],
        issue_number=claim["issue_number"],
        agent_id=claim["agent_id"],
        claimed_at=claim["claimed_at"],
        expires_at=claim["expires_at"],
        branch_name=claim.get("branch_name"),
        pr_number=claim.get("pr_number"),
    )


@router.get("", response_model=list[ClaimOut])
def list_claims(request: Request, repo_slug: str | None = None):
    state = _get_state(request)
    claims = state.db.list_claims(repo_slug)
    return [
        ClaimOut(
            repo_slug=c["repo_slug"],
            issue_number=c["issue_number"],
            agent_id=c["agent_id"],
            claimed_at=c["claimed_at"],
            expires_at=c["expires_at"],
            branch_name=c.get("branch_name"),
            pr_number=c.get("pr_number"),
            expired=bool(c.get("expired")),
        )
        for c in claims
    ]


@router.delete("/{repo_slug:path}/issues/{issue_number}", status_code=204)
def release_claim(repo_slug: str, issue_number: int, request: Request,
                  agent_id: str | None = None):
    state = _get_state(request)

    claim = state.db.get_claim(repo_slug, issue_number)
    if not claim:
        raise HTTPException(404, "Claim not found")

    aid = agent_id or claim["agent_id"]
    state.db.release_claim(repo_slug, issue_number, aid)
