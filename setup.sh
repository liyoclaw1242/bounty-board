#!/bin/bash
# setup.sh — Bootstrap the bounty board system
# Run once per target repo: ./setup.sh owner/repo

set -e

REPO="${1:-}"
if [ -z "$REPO" ]; then
  echo "Usage: ./setup.sh owner/repo"
  echo "Example: ./setup.sh liyoclaw1242/my-project"
  exit 1
fi

echo "🚀 Setting up bounty board for $REPO"

# ── 1. Create GitHub labels ───────────────────────────────────────────────────

echo ""
echo "📌 Creating labels..."

for agent in be fe qa devops; do
  gh label create "agent:$agent" \
    --repo "$REPO" \
    --color "0E8A16" \
    --description "Tasks for $agent agent" \
    --force
  echo "  ✓ agent:$agent"
done

gh label create "status:ready"       --repo "$REPO" --color "0075CA" --description "Ready to be claimed" --force
gh label create "status:blocked"     --repo "$REPO" --color "E4E669" --description "Waiting on dependencies" --force
gh label create "status:in-progress" --repo "$REPO" --color "D93F0B" --description "Agent is working" --force
gh label create "status:review"      --repo "$REPO" --color "5319E7" --description "PR open, awaiting QA" --force

echo "  ✓ status labels"

# ── 2. Local state directory ──────────────────────────────────────────────────

echo ""
echo "📁 Creating ~/.bounty/ ..."
mkdir -p ~/.bounty

# ── 3. Initialize SQLite DB ───────────────────────────────────────────────────

echo "🗄  Initializing claims.db..."
python3 - <<'PYEOF'
import sqlite3, os
db = os.path.expanduser("~/.bounty/claims.db")
conn = sqlite3.connect(db)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("""
CREATE TABLE IF NOT EXISTS claims (
    issue_number INTEGER PRIMARY KEY,
    agent_id     TEXT NOT NULL,
    claimed_at   TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at   TEXT NOT NULL,
    branch_name  TEXT,
    pr_number    INTEGER
)
""")
conn.commit()
conn.close()
print(f"  ✓ {db}")
PYEOF

# ── 4. .env file ──────────────────────────────────────────────────────────────

if [ ! -f ~/.bounty/.env ]; then
  cp .env.example ~/.bounty/.env
  chmod 600 ~/.bounty/.env
  echo "📝 Created ~/.bounty/.env (fill in your GITHUB_TOKEN and paths)"
else
  echo "📝 ~/.bounty/.env already exists, skipping"
fi

# ── 5. Done ───────────────────────────────────────────────────────────────────

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit ~/.bounty/.env — set GITHUB_TOKEN, BOUNTY_REPO, BOUNTY_REPO_DIR"
echo "  2. Create a test issue on $REPO with labels: agent:be, status:ready"
echo "  3. Run: python3 agents/be_agent.py"
echo ""
echo "Agent commands:"
echo "  python3 agents/be_agent.py      # Backend agent"
echo "  python3 agents/fe_agent.py      # Frontend agent"
echo "  python3 agents/qa_agent.py      # QA review agent"
echo "  python3 agents/pm_agent.py      # PM unlock agent"
echo ""
echo "Inspect state:"
echo "  bash scripts/query_claims.sh status"
echo "  bash scripts/query_claims.sh log"
