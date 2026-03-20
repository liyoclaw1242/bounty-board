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

Everything is managed through the REST API:

```bash
# 1. Register a target repo
curl -X POST http://localhost:8000/repos \
  -H "Content-Type: application/json" \
  -d '{"slug": "owner/repo", "github_token": "ghp_..."}'

# 2. Create a bounty (GitHub issue with labels)
curl -X POST http://localhost:8000/bounties \
  -H "Content-Type: application/json" \
  -d '{"repo_slug": "owner/repo", "title": "Add /ping endpoint", "body": "...", "agent_type": "be"}'

# 3. Start an agent worker
curl -X POST http://localhost:8000/agents/start \
  -H "Content-Type: application/json" \
  -d '{"repo_slug": "owner/repo", "agent_type": "be"}'

# 4. Check status
curl http://localhost:8000/health
curl http://localhost:8000/agents
curl http://localhost:8000/claims
```

## Architecture

```
┌─────────────────────────────────────┐
│  Bounty Board (single container)    │
│                                     │
│  FastAPI (:8000)                    │
│    /docs — Swagger UI               │
│    /repos, /bounties, /claims       │
│    /agents — start/stop workers     │
│                                     │
│  Agent workers (background threads) │
│    per repo × per agent type        │
│                                     │
│  SQLite (single writer, no races)   │
└─────────────────────────────────────┘
         │
         ▼  GitHub REST API
   ┌─────────────┐  ┌─────────────┐
   │  repo-a      │  │  repo-b      │
   │  (issues,    │  │  (issues,    │
   │   PRs)       │  │   PRs)       │
   └─────────────┘  └─────────────┘
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/repos` | Register a target repo (clones + creates labels) |
| `GET` | `/repos` | List registered repos |
| `DELETE` | `/repos/{slug}` | Remove repo (stops its workers) |
| `POST` | `/bounties` | Create a bounty (GitHub issue + labels) |
| `GET` | `/bounties` | List bounties (filter by repo, status, agent_type) |
| `GET` | `/bounties/{repo}/issues/{n}` | Get single bounty |
| `PATCH` | `/bounties/{repo}/issues/{n}` | Update status (retry, cancel) |
| `POST` | `/claims` | Manually claim an issue |
| `GET` | `/claims` | List active claims |
| `DELETE` | `/claims/{repo}/issues/{n}` | Release a claim |
| `POST` | `/agents/start` | Start an agent worker |
| `POST` | `/agents/stop` | Stop an agent worker |
| `GET` | `/agents` | List running workers |
| `GET` | `/health` | System health check |

## Agent Types

| Type | Label | Behavior |
|------|-------|----------|
| `be` | `agent:be` | Backend — implements task, pushes branch, opens PR |
| `fe` | `agent:fe` | Frontend — same as BE with React/TS-focused prompt |
| `qa` | `agent:qa` | QA — reviews PRs, approves or requests changes |
| `pm` | `agent:pm` | PM — unlocks blocked issues when deps close |

## Multi-Repo Support

Register multiple repos through the API. Each repo gets its own:
- GitHub labels (created on registration)
- Agent workers (start independently)
- Claims (keyed by `repo_slug + issue_number`)

```bash
# Register two repos
curl -X POST localhost:8000/repos -d '{"slug": "org/api", "github_token": "ghp_..."}'
curl -X POST localhost:8000/repos -d '{"slug": "org/web", "github_token": "ghp_..."}'

# Start agents for each
curl -X POST localhost:8000/agents/start -d '{"repo_slug": "org/api", "agent_type": "be"}'
curl -X POST localhost:8000/agents/start -d '{"repo_slug": "org/web", "agent_type": "fe"}'
```

## Database

Schema: [`db/schema.sql`](db/schema.sql)

```sql
CREATE TABLE repos (
    slug          TEXT PRIMARY KEY,   -- "owner/repo"
    github_token  TEXT NOT NULL,
    repo_dir      TEXT NOT NULL,
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
│   ├── state.py              # AppState (DB, GH clients, workers)
│   ├── routers/
│   │   ├── repos.py          # /repos endpoints
│   │   ├── bounties.py       # /bounties endpoints
│   │   ├── claims.py         # /claims endpoints
│   │   └── agents.py         # /agents endpoints
│   └── workers/
│       ├── base_worker.py    # Stoppable polling thread
│       ├── be_worker.py      # Backend agent
│       ├── fe_worker.py      # Frontend agent
│       ├── qa_worker.py      # QA reviewer
│       └── pm_worker.py      # Dependency unlocker
├── lib/                       # Shared libraries
│   ├── github_client.py       # GitHub API (ETag + rate limits)
│   ├── git_ops.py             # Git operations
│   └── logger.py              # JSONL structured logger
├── agents/                    # Standalone agents (legacy/CLI mode)
├── db/
│   └── schema.sql             # Database schema
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Standalone Mode (Legacy)

The original standalone agents still work for single-repo setups:

```bash
./setup.sh owner/repo
nano ~/.bounty/.env
python3 agents/be_agent.py
```
