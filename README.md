# Bounty Board

Multi-agent software development system. GitHub Issues as task board, local SQLite as mutex, execution agents implement tasks autonomously.

## Architecture

```
OpenClaw PM Agent
│  Creates GitHub Issues, manages labels, unlocks dependencies
↓
GitHub Issues  ←  source of truth
│  Labels: agent:be/fe/qa/devops + status:ready/blocked/in-progress/review
↓
SQLite (~/.bounty/claims.db)  ←  mutex only
│  Atomic claim prevents two agents taking the same task
↓
Execution Agents (local, you activate manually)
│  Poll every 2 min → claim → Claude Code implements → push → open PR
↓
QA Agent  →  reviews PR diff with Claude Code → approve / request changes
↓
You merge  →  GitHub auto-closes issue (Closes #N)  →  PM unlocks downstream
```

## Quick Start

```bash
# 1. Bootstrap labels + local state
./setup.sh owner/your-target-repo

# 2. Configure
nano ~/.bounty/.env   # set GITHUB_TOKEN, BOUNTY_REPO, BOUNTY_REPO_DIR

# 3. Create a test issue on your target repo
#    Labels: agent:be + status:ready

# 4. Start the BE agent
python3 agents/be_agent.py
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
# Backend agent
python3 agents/be_agent.py

# Frontend agent
python3 agents/fe_agent.py

# QA agent (reviews PRs)
python3 agents/qa_agent.py

# PM agent (unlocks blocked issues)
python3 agents/pm_agent.py
```

Run multiple agents in separate terminals. They coordinate automatically via SQLite.

Override agent identity:
```bash
AGENT_ID=be-2 python3 agents/be_agent.py
```

## Dependencies

Use HTML comments in issue body for machine-readable dependencies:

```markdown
## Task
Build the checkout UI form.

## Acceptance Criteria
- [ ] Form validates all fields
- [ ] Calls the `/api/checkout` endpoint (from issue #10)

<!-- deps: 10 -->
```

The `<!-- deps: 10 -->` comment is invisible in rendered markdown.  
The PM agent polls blocked issues every 5 min and unlocks them when all deps close.

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

## Inspecting State

```bash
# Active claims + rate limit
bash scripts/query_claims.sh status

# Recent agent events
bash scripts/query_claims.sh log

# Errors only
bash scripts/query_claims.sh errors
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
| `GITHUB_BOT_USERNAME` | — | — | GitHub username for QA bot (to skip self-reviews) |

## How PR Auto-Close Works

Agents open PRs with `Closes #N` in the description.  
When the PR is merged to `main`, GitHub automatically closes the issue.  
The PM agent detects the closure and unlocks any dependent issues.

> ⚠️  `Closes #N` only works when merging to the **default branch** (main).

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
│   ├── claims.py          # SQLite atomic mutex
│   ├── github_client.py   # GitHub API wrapper (ETag + rate limits)
│   ├── git_ops.py         # git operations
│   └── logger.py          # JSONL structured logger
├── scripts/
│   └── query_claims.sh    # inspect claims.db + agent.log
├── setup.sh               # bootstrap script
└── .env.example           # config template
```
