#!/usr/bin/env bash
# play.sh — one-command demo runner for Kestra Hackathon Co-Pilot.
#
# Usage:
#   ./play.sh                                # uses the default whiteboard brief
#   ./play.sh "Build a CLI todo app …"       # custom brief
#   ./play.sh --warmup                       # do a throwaway run first to warm caches
#   ./play.sh --open                         # also open Kestra UI / Obsidian / Slack tabs
#
# This is the script you run while the screen recorder is rolling.

set -euo pipefail
cd "$(dirname "$0")"

# ── Config (override with env if you want) ──────────────────────────
KESTRA_URL="${KESTRA_URL:-http://localhost:18080}"
KESTRA_USER="${KESTRA_USER:-admin@kestra.local}"
KESTRA_PASS="${KESTRA_PASS:-Hackathon2026!}"
NAMESPACE="${NAMESPACE:-hackathon.copilot}"
DEFAULT_BRIEF="Build a real-time collaborative whiteboard with WebSockets and Postgres"
VAULT_DIR="${OBSIDIAN_VAULT_PATH:-/home/pavan/Documents/KestraCoPilotVault}/kestra-copilot"

WARMUP=0
OPEN=0
BRIEF=""
for arg in "$@"; do
  case "$arg" in
    --warmup) WARMUP=1 ;;
    --open)   OPEN=1 ;;
    --help|-h)
      sed -n '2,15p' "$0"
      exit 0
      ;;
    *) BRIEF="$arg" ;;
  esac
done
BRIEF="${BRIEF:-$DEFAULT_BRIEF}"

# ── Pre-flight ──────────────────────────────────────────────────────
echo "── pre-flight ───────────────────────────────────────────"
HTTP=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 4 "$KESTRA_URL/api/v1/configs" || echo "000")
if [[ "$HTTP" != "200" ]]; then
  echo "✗ Kestra is not reachable at $KESTRA_URL (got $HTTP). Run: docker compose up -d"
  exit 1
fi
echo "✓ Kestra UP at $KESTRA_URL"

FLOW_COUNT=$(curl -sS -u "$KESTRA_USER:$KESTRA_PASS" \
  "$KESTRA_URL/api/v1/main/flows/search?namespace=$NAMESPACE&size=20" \
  | python3 -c "import json,sys;print(len(json.load(sys.stdin).get('results',[])))")
echo "✓ $FLOW_COUNT flows deployed in $NAMESPACE"
[[ "$FLOW_COUNT" -lt 6 ]] && {
  echo "  (expected 6: setup, planner, researcher, coder, reviewer, communicator. Run: kestractl flows deploy ./flows/ --override)"
}

# ── Optional warmup (throwaway run to prime LLM/Docker caches) ──────
if [[ "$WARMUP" == "1" ]]; then
  echo ""
  echo "── warmup ───────────────────────────────────────────────"
  echo "Triggering a warmup run (output discarded, caches primed)…"
  curl -sS -u "$KESTRA_USER:$KESTRA_PASS" \
    -X POST "$KESTRA_URL/api/v1/main/executions/$NAMESPACE/planner?wait=true" \
    -F "goal=Print hello world from a Python script." \
    -o /dev/null -w "  warmup state: %{http_code}\n"
  sleep 2
  echo "✓ warmup done"
fi

# ── Optional: open the 3-pane recording surface ─────────────────────
if [[ "$OPEN" == "1" ]]; then
  echo ""
  echo "── opening browser tabs (3-pane recording layout) ───────"
  for url in \
    "$KESTRA_URL/ui/main/executions?filters=namespace%3A$NAMESPACE&sort=startDate:desc" \
    "obsidian://open?vault=KestraCoPilotVault&file=kestra-copilot%2FREADME"
  do
    if command -v xdg-open >/dev/null 2>&1; then xdg-open "$url" >/dev/null 2>&1 &
    elif command -v open >/dev/null 2>&1; then open "$url" >/dev/null 2>&1 &
    fi
  done
  echo "✓ tabs spawning. Position: Kestra (left half), Obsidian (top right), Slack (bottom right)."
  sleep 2
fi

# ── The real run ────────────────────────────────────────────────────
echo ""
echo "── triggering planner ────────────────────────────────────"
echo "  brief: $BRIEF"
echo ""
START=$(date +%s)
RESP=$(curl -sS -u "$KESTRA_USER:$KESTRA_PASS" \
  -X POST "$KESTRA_URL/api/v1/main/executions/$NAMESPACE/planner?wait=true" \
  -F "goal=$BRIEF")
END=$(date +%s)

EXEC_ID=$(echo "$RESP" | python3 -c "import json,sys;print(json.load(sys.stdin).get('id',''))")
STATE=$(echo "$RESP" | python3 -c "import json,sys;print(json.load(sys.stdin).get('state',{}).get('current',''))")
DURATION=$(echo "$RESP" | python3 -c "import json,sys;print(json.load(sys.stdin).get('state',{}).get('duration',''))")

echo "── result ───────────────────────────────────────────────"
printf "  exec_id:   %s\n" "$EXEC_ID"
printf "  state:     %s\n" "$STATE"
printf "  duration:  %s   (%ss wallclock)\n" "$DURATION" "$((END-START))"
echo ""
echo "  children:"
sleep 2
curl -sS -u "$KESTRA_USER:$KESTRA_PASS" \
  "$KESTRA_URL/api/v1/main/executions/search?namespace=$NAMESPACE&labels=copilot_goal_id:$EXEC_ID&size=10" \
  | python3 -c "
import json,sys
d = json.load(sys.stdin)
for r in sorted(d.get('results', []), key=lambda x: x['state']['startDate']):
    print(f\"    {r['flowId']:<14} {r['state']['current']:<10} dur={r['state'].get('duration','?')}\")"

# ── Surface the produced artifacts ──────────────────────────────────
echo ""
echo "── artifacts ────────────────────────────────────────────"
LATEST_REPORT=$(ls -t "$VAULT_DIR"/reports/*.md 2>/dev/null | head -1 || true)
if [[ -n "$LATEST_REPORT" ]]; then
  echo "  📝 latest report: $LATEST_REPORT"
  REPO_URL=$(grep "^repo_url:" "$LATEST_REPORT" | head -1 | cut -d' ' -f2-)
  [[ -n "$REPO_URL" && "$REPO_URL" != "(none)" ]] && echo "  🐙 repo:          $REPO_URL"
fi
echo "  🔗 kestra ui:     $KESTRA_URL/ui/main/executions/$EXEC_ID"
echo ""
echo "Done."
