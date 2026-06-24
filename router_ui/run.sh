#!/usr/bin/env bash
# Router memory-inspector UI launcher.
#
# Inspects the memories the cookbook-memory plugin saves during a benchmark run and lets you
# evaluate how the router routed them. Runs from the agent-memory-harness dir (so newest
# results/v*/_memory auto-discovery works) using that repo's venv (which provides `memeval`),
# with this workspace on PYTHONPATH (which provides `router_ui`).
#
#   ./router_ui/run.sh                      # newest harness pipeline substrate
#   ./router_ui/run.sh --seed --open        # synthetic demo corpus (no real run needed)
#   ./router_ui/run.sh --store /path/_memory
set -euo pipefail
HARNESS=/home/brent-gibson/projects/agent-memory-harness
HERE="$(cd "$(dirname "$0")/.." && pwd)"   # capstone-workspace (parent of router_ui/)
cd "$HARNESS"
exec env PYTHONPATH="$HERE" "$HARNESS/.venv/bin/python" -m router_ui "$@"
