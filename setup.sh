#!/bin/bash
# setup.sh — Bootstrap the bounty board system
# Run once per target repo: ./setup.sh owner/repo

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

REPO="${1:-}"
if [ -z "$REPO" ]; then
  echo "Usage: ./setup.sh owner/repo"
  echo "Example: ./setup.sh liyoclaw1242/my-project"
  exit 1
fi

# ── 0. Prerequisites ─────────────────────────────────────────────────────────

echo "🔍 Checking prerequisites..."

MISSING=0

check_cmd() {
  if ! command -v "$1" &>/dev/null; then
    echo "  ✗ $1 — $2"
    MISSING=1
  else
    echo "  ✓ $1"
  fi
}

check_cmd git      "Install: https://git-scm.com"
check_cmd gh       "Install: brew install gh  (or https://cli.github.com)"
check_cmd python3  "Install: brew install python3  (requires 3.10+)"
check_cmd claude   "Install: npm install -g @anthropic-ai/claude-code"
check_cmd jq       "Install: brew install jq  (optional, for query_claims.sh)"

# Check Python version >= 3.10
if command -v python3 &>/dev/null; then
  PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
  PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
  PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
  if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo "  ✗ python3 version $PY_VER (requires 3.10+)"
    MISSING=1
  fi
fi

# Check requests module
if command -v python3 &>/dev/null; then
  if python3 -c "import requests" &>/dev/null; then
    echo "  ✓ python3 requests module"
  else
    echo "  ✗ python3 requests module — pip install -r requirements.txt"
    MISSING=1
  fi
fi

# Check gh auth
if command -v gh &>/dev/null; then
  if gh auth status &>/dev/null; then
    echo "  ✓ gh authenticated"
  else
    echo "  ✗ gh not authenticated — run: gh auth login"
    MISSING=1
  fi
fi

if [ "$MISSING" -eq 1 ]; then
  echo ""
  echo "❌ Missing prerequisites. Install them and re-run."
  exit 1
fi

echo ""
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
python3 -c "
import sqlite3, os
db = os.path.expanduser('~/.bounty/claims.db')
conn = sqlite3.connect(db)
with open('$SCRIPT_DIR/db/schema.sql') as f:
    conn.executescript(f.read())
conn.commit()
conn.close()
print(f'  ✓ {db}')
"

# ── 4. .env file ──────────────────────────────────────────────────────────────

if [ ! -f ~/.bounty/.env ]; then
  cp "$SCRIPT_DIR/.env.example" ~/.bounty/.env
  chmod 600 ~/.bounty/.env
  echo "📝 Created ~/.bounty/.env (fill in your GITHUB_TOKEN and paths)"
else
  echo "📝 ~/.bounty/.env already exists, skipping"
fi

# ── 5. Validate ───────────────────────────────────────────────────────────────

echo ""
echo "🧪 Validating..."

# Check repo accessibility
if gh repo view "$REPO" --json name &>/dev/null; then
  echo "  ✓ repo $REPO accessible"
else
  echo "  ⚠ repo $REPO not accessible (check token permissions)"
fi

# Check DB
CLAIM_COUNT=$(python3 -c "
import sqlite3, os
db = os.path.expanduser('~/.bounty/claims.db')
conn = sqlite3.connect(db)
count = conn.execute('SELECT COUNT(*) FROM claims').fetchone()[0]
print(count)
conn.close()
")
echo "  ✓ claims.db initialized ($CLAIM_COUNT active claims)"

# ── 6. Done ───────────────────────────────────────────────────────────────────

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
echo "  python3 lib/claims.py status"
echo "  bash scripts/query_claims.sh status"
echo "  bash scripts/query_claims.sh log"
