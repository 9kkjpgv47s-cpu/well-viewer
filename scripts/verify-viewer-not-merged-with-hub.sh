#!/usr/bin/env bash
# Fail if root index.html contains Drill Hub–only markers (projects crossed).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HTML="$ROOT/index.html"
if [[ ! -f "$HTML" ]]; then
  echo "verify-viewer-not-merged-with-hub: missing $HTML" >&2
  exit 1
fi
MARKERS=(
  "CJ_DRILLER_JOB_KEY"
  "cj-hub-bar"
  "cjSwitchHubTab"
  "cjRenderDrillerPanel"
)
bad=0
for s in "${MARKERS[@]}"; do
  if grep -q "$s" "$HTML"; then
    echo "verify-viewer-not-merged-with-hub: forbidden hub marker in index.html: $s" >&2
    bad=1
  fi
done
if [[ "$bad" -ne 0 ]]; then
  echo "Remove Drill Hub UI/scripts from this repo's index.html, or use the hub repo + sync into public/well-viewer/ only." >&2
  exit 1
fi
echo "verify-viewer-not-merged-with-hub: OK (no hub markers in index.html)"
