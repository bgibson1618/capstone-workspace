#!/usr/bin/env bash
# reseed-sandbox.sh — fix the recurring "pipeline sandbox not logged in" error.
#
# Root cause: `make pipeline` drives the claude CLI against an ISOLATED config at
# agent-memory-harness/eval/.claude-sandbox. Running `/login` there while an
# ANTHROPIC_BASE_URL is set (an open-* shell func) authenticates in API-key mode and
# writes an EMPTY OAuth block -> "not logged in". `claude-reset` does NOT unset BASE_URL.
# The seeded token also expires (~8h), so it recurs the next day.
#
# Fix: copy your VALID host OAuth credential into the sandbox (bypasses /login entirely).
# DO NOT `/login` the sandbox — re-seed instead.
#
# Usage:  bash tools/reseed-sandbox.sh
#         SANDBOX=/path/to/eval/.claude-sandbox bash tools/reseed-sandbox.sh   # override path
set -euo pipefail

HOST_CRED="${HOST_CRED:-$HOME/.claude/.credentials.json}"
SANDBOX="${SANDBOX:-$HOME/projects/agent-memory-harness/eval/.claude-sandbox}"
SBX_CRED="$SANDBOX/.credentials.json"

# 1. Warn on the env trap (these break a real login + can misroute the run).
trap_hit=0
for v in ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN ANTHROPIC_API_KEY; do
  if [ -n "${!v:-}" ]; then echo "⚠️  $v is set — run 'claude-reset' (and unset ANTHROPIC_BASE_URL) before the pipeline"; trap_hit=1; fi
done

# 2. Verify the HOST cred is a valid, unexpired OAuth login before copying.
python3 - "$HOST_CRED" <<'PY'
import json, sys, time
p = sys.argv[1]
try: d = json.load(open(p))
except Exception as e: sys.exit(f"✗ host cred unreadable ({p}): {e}")
oa = d.get("claudeAiOauth") or {}
if not oa.get("accessToken") or not oa.get("refreshToken"):
    sys.exit(f"✗ host cred has no real OAuth tokens — run a real `claude` /login on the HOST first ({p})")
exp = oa.get("expiresAt", 0); mins = (exp - time.time()*1000)/60000
if mins <= 0: sys.exit(f"✗ host token EXPIRED — re-login the host claude session first")
print(f"✓ host cred valid (+{mins:.0f} min)")
PY

# 3. Seed the sandbox from the host cred.
[ -d "$SANDBOX" ] || { echo "✗ sandbox dir not found: $SANDBOX"; exit 1; }
[ -f "$SBX_CRED" ] && cp -p "$SBX_CRED" "$SBX_CRED.bak" 2>/dev/null || true
cp "$HOST_CRED" "$SBX_CRED"
chmod 600 "$SBX_CRED"

# 4. Confirm.
python3 - "$SBX_CRED" <<'PY'
import json, sys, time
oa = json.load(open(sys.argv[1])).get("claudeAiOauth") or {}
mins = (oa.get("expiresAt",0) - time.time()*1000)/60000
print(f"✓ sandbox re-seeded — accessToken:{bool(oa.get('accessToken'))} expiry:+{mins:.0f} min")
PY
echo "Done. Run the pipeline from this shell (ANTHROPIC_* unset). Do NOT /login the sandbox."
[ "$trap_hit" = 1 ] && echo "(reminder: clear the ANTHROPIC_* vars first — see warning above)" || true
