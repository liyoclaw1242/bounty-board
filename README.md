# Bounty Board

Multi-agent software development system. GitHub Issues as task board, REST API for orchestration, Claude Code agents implement tasks autonomously.

## Quick Start

### Local

```bash
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

### Docker

```bash
docker compose up -d
```

Open **http://localhost:8000/docs** for Swagger UI.

## Usage

### 1. Register a repo

```bash
curl -X POST http://localhost:8000/repos \
  -H "Content-Type: application/json" \
  -d '{"slug": "owner/repo", "github_token": "ghp_..."}'
```

When the API server runs inside Docker, the auto-assigned `repo_dir` is a container-internal path (e.g. `/data/repos/owner/repo`). If your agents run on the **host**, pass `local_dir` so they know where the clone lives on the host filesystem:

```bash
curl -X POST http://localhost:8000/repos \
  -H "Content-Type: application/json" \
  -d '{"slug": "owner/repo", "github_token": "ghp_...", "local_dir": "~/Projects/repo"}'
```

The `GET /repos` response includes both `repo_dir` (server-side) and `local_dir` (host-side). Agents should prefer `local_dir` when available.

### 2. Create a bounty

```bash
curl -X POST http://localhost:8000/bounties \
  -H "Content-Type: application/json" \
  -d '{"repo_slug": "owner/repo", "title": "Add /ping endpoint", "body": "...", "agent_type": "be"}'
```

### 3. Start agents (manually)

Agents are started by humans — you decide how many to run. Each agent is a separate process that polls the API for work, claims a task, runs Claude Code, and opens a PR.

```bash
# Open a terminal and start a backend agent
python3 agents/be_agent.py

# Open another terminal for QA
python3 agents/qa_agent.py

# Scale up — run multiple agents in parallel
AGENT_ID=be-2 python3 agents/be_agent.py
```

Agents are the **consumers** of the API, not managed by it.

### 4. Check status

```bash
curl http://localhost:8000/health
curl http://localhost:8000/claims
curl http://localhost:8000/bounties?repo_slug=owner/repo&status=ready
```

## Architecture

```
Human (you)
│  Starts/stops agent processes manually
│
├──→ Agent (be_agent.py)  ──┐
├──→ Agent (fe_agent.py)  ──┤
├──→ Agent (qa_agent.py)  ──┤  Each agent is a separate process
└──→ Agent (pm_agent.py)  ──┤  running Claude Code
                            │
                            ▼
                 ┌──────────────────┐
                 │  API Server      │
                 │  FastAPI (:8000) │
                 │  /docs (Swagger) │
                 │                  │
                 │  /repos          │  CRUD
                 │  /bounties       │  CRUD
                 │  /claims         │  Mutex
                 │  /health         │
                 │                  │
                 │  SQLite          │
                 └────────┬─────────┘
                          │
                          ▼  GitHub REST API
                   ┌──────────┐  ┌──────────┐
                   │  repo-a   │  │  repo-b   │
                   └──────────┘  └──────────┘
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/repos` | Register a target repo (clones + creates labels) |
| `GET` | `/repos` | List registered repos |
| `DELETE` | `/repos/{slug}` | Remove a repo |
| `POST` | `/bounties` | Create a bounty (GitHub issue + labels) |
| `GET` | `/bounties` | List bounties (filter by repo, status, agent_type) |
| `GET` | `/bounties/{repo}/issues/{n}` | Get single bounty |
| `PATCH` | `/bounties/{repo}/issues/{n}` | Update status (retry, cancel) |
| `POST` | `/claims` | Claim an issue (atomic mutex) |
| `GET` | `/claims` | List active claims |
| `DELETE` | `/claims/{repo}/issues/{n}` | Release a claim |
| `GET` | `/health` | System health check |

## How Claims Work

Claims prevent two agents from working on the same task:

```
Agent A: POST /claims {"repo_slug": "org/api", "issue_number": 5, "agent_id": "be-1"}
→ 201 Created (claimed)

Agent B: POST /claims {"repo_slug": "org/api", "issue_number": 5, "agent_id": "be-2"}
→ 409 Conflict (already claimed)

Agent A finishes: DELETE /claims/org/api/issues/5
→ 204 (released, available again)
```

Claims have a TTL (default 2 hours). If an agent crashes without releasing, the claim expires automatically and another agent can pick it up.

## Agent Types

| Type | Label | Behavior |
|------|-------|----------|
| `be` | `agent:be` | Backend — implements task, pushes branch, opens PR |
| `fe` | `agent:fe` | Frontend — same as BE with React/TS-focused prompt |
| `qa` | `agent:qa` | QA — reviews PRs, approves or requests changes |
| `pm` | `agent:pm` | PM — unlocks blocked issues when deps close |

## Agent Lifecycle

Each agent runs an infinite loop:

```
┌──→ Poll API for status:ready issues matching its label
│    │
│    ├── Found one → POST /claims (try to claim)
│    │   ├── 201 → Run Claude Code → git push → open PR → DELETE /claims
│    │   └── 409 → Someone else got it, try next
│    │
│    └── None found → Backoff (2 min → 10 min max)
│
└── Sleep → repeat
```

Agents are designed to be disposable. Kill one anytime (Ctrl+C), start more anytime. The mutex ensures no duplicate work.

## Multi-Repo Support

Register multiple repos through the API. Claims are keyed by `(repo_slug, issue_number)` so issue numbers never collide across repos.

```bash
curl -X POST localhost:8000/repos -H "Content-Type: application/json" \
  -d '{"slug": "org/api", "github_token": "ghp_..."}'
curl -X POST localhost:8000/repos -H "Content-Type: application/json" \
  -d '{"slug": "org/web", "github_token": "ghp_..."}'
```

## Database

Schema: [`db/schema.sql`](db/schema.sql)

```sql
CREATE TABLE repos (
    slug          TEXT PRIMARY KEY,   -- "owner/repo"
    github_token  TEXT NOT NULL,
    repo_dir      TEXT NOT NULL,      -- server-side path
    local_dir     TEXT,               -- host-side path (for agents outside container)
    bot_username  TEXT DEFAULT '',
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE claims (
    repo_slug    TEXT    NOT NULL,
    issue_number INTEGER NOT NULL,
    agent_id     TEXT    NOT NULL,
    claimed_at   TEXT    DEFAULT (datetime('now')),
    expires_at   TEXT    NOT NULL,
    branch_name  TEXT,
    pr_number    INTEGER,
    PRIMARY KEY (repo_slug, issue_number)
);
```

## Issue Spec Format

```markdown
## Task
[What to build]

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Files Likely Affected
- src/api/foo.ts

<!-- deps: 10, 12 -->   ← blocks until #10 and #12 close
```

## Label Schema

| Label | Meaning |
|-------|---------|
| `agent:be` / `fe` / `qa` / `devops` | Task assignment |
| `status:ready` | Available to claim |
| `status:blocked` | Waiting on dependencies |
| `status:in-progress` | Agent working |
| `status:review` | PR open, awaiting QA |

## Docker Data

All persistent state is bind-mounted to the host:

```
~/.bounty/server/
├── bounty.db         # SQLite database
├── agent.log         # JSONL event log
└── repos/            # Cloned target repos
    ├── owner/repo-a/
    └── owner/repo-b/
```

## File Structure

```
bounty-board/
├── app/
│   ├── main.py              # FastAPI app + lifespan
│   ├── config.py             # Settings (env vars)
│   ├── database.py           # Thread-safe SQLite wrapper
│   ├── models.py             # Pydantic request/response models
│   ├── state.py              # AppState (DB, GH clients)
│   └── routers/
│       ├── repos.py          # /repos endpoints
│       ├── bounties.py       # /bounties endpoints
│       └── claims.py         # /claims endpoints
├── lib/                       # Shared libraries
│   ├── github_client.py       # GitHub API (ETag + rate limits)
│   ├── git_ops.py             # Git operations
│   └── logger.py              # JSONL structured logger
├── agents/                    # Agent processes (started by humans)
│   ├── base_agent.py          # Shared polling + claim + Claude Code
│   ├── be_agent.py            # Backend agent
│   ├── fe_agent.py            # Frontend agent
│   ├── qa_agent.py            # QA review agent
│   └── pm_agent.py            # Dependency unlock agent
├── db/
│   └── schema.sql             # Database schema
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```
