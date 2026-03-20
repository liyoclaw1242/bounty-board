#!/bin/bash
# query_claims.sh — Inspect bounty board state
# Usage: bash scripts/query_claims.sh [status|log|errors|recent]

DB="${BOUNTY_DB:-$HOME/.bounty/claims.db}"
LOG="${BOUNTY_LOG:-$HOME/.bounty/agent.log}"
CMD="${1:-status}"

case "$CMD" in
  status)
    echo "=== Active Claims ==="
    sqlite3 "$DB" -column -header \
      "SELECT issue_number, agent_id, claimed_at, expires_at, branch_name, pr_number,
              CASE WHEN expires_at < datetime('now') THEN '⚠️  EXPIRED' ELSE '✓ active' END as state
       FROM claims ORDER BY claimed_at DESC;"
    echo ""
    echo "=== Rate Limit ==="
    if [ -n "$GITHUB_TOKEN" ]; then
      curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
        https://api.github.com/rate_limit | python3 -c "
import json,sys
d=json.load(sys.stdin)['rate']
print(f\"  core: {d['remaining']}/{d['limit']} (resets at {d['reset']})\")
"
    else
      echo "  (set GITHUB_TOKEN to check)"
    fi
    ;;

  log)
    echo "=== Last 30 Events ==="
    tail -30 "$LOG" 2>/dev/null | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        e = json.loads(line)
        print(f\"{e['ts'][:19]} [{e['agent']:>6}] {e['event']:<16} {e.get('issue','') or e.get('pr','')}\")
    except: pass
"
    ;;

  errors)
    echo "=== Errors ==="
    grep '"event": "error"' "$LOG" 2>/dev/null | tail -20 | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        e = json.loads(line)
        print(f\"{e['ts'][:19]} [{e['agent']}] {e.get('exc','')[:100]}\")
    except: pass
"
    ;;

  recent)
    echo "=== Last 10 Events (raw) ==="
    tail -10 "$LOG" 2>/dev/null | python3 -m json.tool --no-ensure-ascii 2>/dev/null || \
    tail -10 "$LOG" 2>/dev/null
    ;;

  *)
    echo "Usage: $0 [status|log|errors|recent]"
    ;;
esac
