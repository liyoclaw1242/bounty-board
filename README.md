# Bounty Board

Multi-agent software development system. GitHub Issues as task board, local SQLite as mutex, Claude Code agents implement tasks autonomously.

## Prerequisites

| Tool | Install |
|------|---------|
| Python 3.10+ | `brew install python3` |
| Git | `brew install git` |
| [GitHub CLI](https://cli.github.com) | `brew install gh` then `gh auth login` |
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | `npm install -g @anthropic-ai/claude-code` |
| jq (optional) | `brew install jq` |

```bash
pip install -r requirements.txt
```

## Quick Start

```bash
# 1. Clone this repo
git clone https://github.com/liyoclaw1242/bounty-board.git
cd bounty-board

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Prepare your target repo on GitHub (the repo agents will work on)
#    Clone it locally, e.g. ~/Projects/my-app

# 4. Bootstrap — creates labels on the target repo, initializes local DB + config
./setup.sh owner/your-target-repo

# 5. Configure
nano ~/.bounty/.env   # set GITHUB_TOKEN, BOUNTY_REPO, BOUNTY_REPO_DIR

# 6. Create a test issue on your target repo
#    Labels: agent:be + status:ready

# 7. Start an agent
python3 agents/be_agent.py
```

`setup.sh` will check all prerequisites before proceeding and tell you what's missing.

## Architecture

```
GitHub Issues  ←  source of truth (labels = task state)
│  Labels: agent:be/fe/qa/devops + status:ready/blocked/in-progress/review
↓
SQLite (~/.bounty/claims.db)  ←  mutex only (prevents double-claiming)
↓
Execution Agents (local, you activate manually)
│  Poll every 2 min → claim → Claude Code implements → push → open PR
↓
QA Agent  →  reviews PR diff with Claude Code → APPROVE / REQUEST_CHANGES
↓
You merge  →  GitHub auto-closes issue (Closes #N)  →  PM unlocks downstream
```

## Label Schema

| Label | Meaning |
|-------|---------|
| `agent:be` | Backend task |
| `agent:fe` | Frontend task |
| `agent:qa` | QA / testing task |
| `agent:devops` | Infrastructure / CI task |
| `status:ready` | Available to claim |
| `status:blocked` | Waiting on dependencies |
| `status:in-progress` | Agent working on it |
| `status:review` | PR open, awaiting QA |

## Running Agents

```bash
python3 agents/be_agent.py        # Backend agent
python3 agents/fe_agent.py        # Frontend agent
python3 agents/qa_agent.py        # QA agent (reviews PRs)
python3 agents/pm_agent.py        # PM agent (unlocks blocked issues)
```

Run multiple agents in separate terminals. They coordinate automatically via SQLite.

Override agent identity:
```bash
AGENT_ID=be-2 python3 agents/be_agent.py
```

## Database

Schema: [`db/schema.sql`](db/schema.sql)

SQLite is used as an **atomic mutex**, not a state machine. A row in `claims` means an agent is working on that issue; deleting the row releases it. Claims expire after 2 hours (crash recovery).

```sql
CREATE TABLE claims (
    issue_number INTEGER PRIMARY KEY,
    agent_id     TEXT NOT NULL,
    claimed_at   TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at   TEXT NOT NULL,
    branch_name  TEXT,
    pr_number    INTEGER
);
```

## Issue Spec Format

For best results, structure issues like this:

```markdown
## Task
[One-sentence description of what to build]

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Files Likely Affected
- src/api/foo.ts
- tests/api/foo.test.ts

## Context
[Any relevant background, API contracts, or links]

<!-- deps: 10, 12 -->   ← only if blocked by other issues
```

## Dependencies Between Issues

Use HTML comments in issue body for machine-readable dependencies:

```markdown
<!-- deps: 10 -->
```

The comment is invisible in rendered markdown. The PM agent polls `status:blocked` issues every 5 min and flips them to `status:ready` when all deps close.

## Inspecting State

```bash
python3 lib/claims.py status              # Active claims

bash scripts/query_claims.sh status       # Claims + rate limit
bash scripts/query_claims.sh log          # Recent agent events
bash scripts/query_claims.sh errors       # Errors only
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GITHUB_TOKEN` | ✓ | — | Fine-grained PAT (Issues + PRs + Contents on target repo) |
| `BOUNTY_REPO` | ✓ | — | `owner/repo` to work on |
| `BOUNTY_REPO_DIR` | ✓ | — | Local path to the target repo |
| `BOUNTY_DB` | — | `~/.bounty/claims.db` | SQLite path |
| `BOUNTY_LOG` | — | `~/.bounty/agent.log` | JSONL log path |
| `AGENT_ID` | — | `be-1` / `fe-1` etc. | Override agent identity |
| `GITHUB_BOT_USERNAME` | — | — | GitHub username (for QA to skip self-reviews) |

## How PR Auto-Close Works

Agents open PRs with `Closes #N` in the description.
When the PR is merged to `main`, GitHub automatically closes the issue.
The PM agent detects the closure and unlocks any dependent issues.

> `Closes #N` only works when merging to the **default branch** (main).

## v1 Rules

- **Human merges all PRs** — QA agent approves, you click merge
- **One token** — all agents share one fine-grained PAT
- **Single machine** — SQLite mutex requires all agents on same host
- **No auto-merge** — add this in v2 after the system proves reliable

## File Structure

```
bounty-board/
├── agents/
│   ├── base_agent.py      # shared polling + claim + Claude Code logic
│   ├── be_agent.py        # backend agent
│   ├── fe_agent.py        # frontend agent
│   ├── qa_agent.py        # PR review agent
│   └── pm_agent.py        # dependency unlock agent
├── lib/
│   ├── claims.py          # SQLite atomic mutex + CLI
│   ├── github_client.py   # GitHub API wrapper (ETag + rate limits)
│   ├── git_ops.py         # git operations
│   └── logger.py          # JSONL structured logger
├── db/
│   └── schema.sql         # database schema
├── scripts/
│   └── query_claims.sh    # inspect claims.db + agent.log
├── setup.sh               # bootstrap script (checks prerequisites)
├── requirements.txt       # Python dependencies
└── .env.example           # config template
```
