#!/usr/bin/env bash
# Local DNR data pipeline (replaces a one-off script that never lived in git).
#
# Important: build_statewide_data.py only merges HTML lithology / cache when
# DNR_FILL_LITHO_HTML=1 (or related flags). A plain rebuild does NOT apply
# dnr_html_litho_cache.json by itself — so this script never runs "rebuild"
# twice in one invocation.
#
# Usage:
#   ./run_dnr_pipeline_local.sh                    # preflight + rebuild (WellLogs only unless you export flags)
#   RUN_HTML_BACKFILL=1 ./run_dnr_pipeline_local.sh   # preflight + ONE full build with HTML (set DNR_HTML_LITHO_* too)
#
# Optional env:
#   DNR_PREFLIGHT_REF   default 174349 (only if debug_dnr_html.py exists)
#   DNR_OUT_DIR         default: this directory
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export DNR_OUT_DIR="${DNR_OUT_DIR:-$ROOT}"

echo "== [1/3] Environment + optional preflight =="
echo "  cwd: $ROOT"
echo "  DNR_OUT_DIR: $DNR_OUT_DIR"
echo "  RUN_HTML_BACKFILL: ${RUN_HTML_BACKFILL:-0}"
if [[ -n "${DNR_HTTP_COOKIE:-}" ]]; then
  echo "  DNR_HTTP_COOKIE: (set)"
else
  echo "  DNR_HTTP_COOKIE: (unset)"
fi

python3 -c "from dnr_env_local import ensure_dnr_env_local_loaded; ensure_dnr_env_local_loaded()" 2>/dev/null || true

PREFLIGHT_REF="${DNR_PREFLIGHT_REF:-174349}"
if [[ -f "$ROOT/debug_dnr_html.py" ]]; then
  echo "  Running preflight (ref $PREFLIGHT_REF)…"
  python3 "$ROOT/debug_dnr_html.py" "$PREFLIGHT_REF" --save-default
else
  echo "  No debug_dnr_html.py in this folder — preflight skipped."
  echo "  Sample: python3 debug_dnr_html.py ${PREFLIGHT_REF} --save-default"
fi

echo ""
echo "== [2/3] HTML lithology / modal fetch (optional) =="
if [[ "${RUN_HTML_BACKFILL:-}" == "1" ]]; then
  export DNR_FILL_LITHO_HTML=1
  echo "  DNR_FILL_LITHO_HTML=1 — statewide needs DNR_HTML_LITHO_UNLIMITED=1 or DNR_HTML_LITHO_MAX=N"
  echo "  Running a single rebuild (writes chunks at end; step [3/3] will be skipped)…"
  python3 "$ROOT/rebuild_viewer_data.py"
  echo ""
  echo "== [3/3] Skipped (chunks already written in step 2) =="
  echo "  Done."
  exit 0
fi

echo "  Skipping HTML backfill (set RUN_HTML_BACKFILL=1 to enable network HTML pass)."
echo "  NOTE: This rebuild uses WellLogs CSV + placeholders unless you already exported DNR_FILL_LITHO_HTML=1 etc."

echo ""
echo "== [3/3] Rebuild gz chunks (WellLogs + env-driven HTML if any) =="
python3 "$ROOT/rebuild_viewer_data.py"
echo "Done."
