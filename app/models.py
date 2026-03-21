from pydantic import BaseModel


# ── Request models ────────────────────────────────────────────────────────────

class RepoCreate(BaseModel):
    slug: str                        # "owner/repo"
    github_token: str
    repo_dir: str | None = None      # auto-assigned if omitted
    local_dir: str | None = None     # host-side path for agents outside container
    bot_username: str = ""

class BountyCreate(BaseModel):
    repo_slug: str
    title: str
    body: str
    agent_type: str                  # "be", "fe", "qa", "devops"
    deps: list[int] = []

class BountyUpdate(BaseModel):
    status: str | None = None        # "ready", "blocked", "in-progress", "review"

class ClaimCreate(BaseModel):
    repo_slug: str
    issue_number: int
    agent_id: str
    ttl_hours: int = 2


# ── Response models ───────────────────────────────────────────────────────────

class RepoOut(BaseModel):
    slug: str
    repo_dir: str
    local_dir: str | None = None     # host-side path; falls back to repo_dir if unset
    bot_username: str
    created_at: str

class ClaimOut(BaseModel):
    repo_slug: str
    issue_number: int
    agent_id: str
    claimed_at: str
    expires_at: str
    branch_name: str | None
    pr_number: int | None
    expired: bool = False

class HealthOut(BaseModel):
    status: str
    repos: int
    active_claims: int
