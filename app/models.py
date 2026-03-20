from pydantic import BaseModel


# ── Request models ────────────────────────────────────────────────────────────

class RepoCreate(BaseModel):
    slug: str                        # "owner/repo"
    github_token: str
    repo_dir: str | None = None      # auto-assigned if omitted
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

class AgentStart(BaseModel):
    repo_slug: str
    agent_type: str                  # "be", "fe", "qa", "pm"
    agent_id: str | None = None

class AgentStop(BaseModel):
    agent_id: str


# ── Response models ───────────────────────────────────────────────────────────

class RepoOut(BaseModel):
    slug: str
    repo_dir: str
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

class AgentOut(BaseModel):
    agent_id: str
    agent_type: str
    repo_slug: str
    status: str                      # "running", "stopping", "stopped"
    started_at: str

class HealthOut(BaseModel):
    status: str
    repos: int
    active_claims: int
    active_agents: int
