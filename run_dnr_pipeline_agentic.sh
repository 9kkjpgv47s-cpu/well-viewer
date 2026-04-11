#!/usr/bin/env bash
# Agentic statewide lithology pipeline:
# - validates HTML parsing with a pilot sample
# - auto-retries with safer HTTP headers
# - warns early for stale/bad cache patterns
# - only then runs full statewide rebuild + optional modal meta backfill
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

export DNR_OUT_DIR="${DNR_OUT_DIR:-$ROOT}"
export DNR_FILL_LITHO_HTML=1
export DNR_HTML_LITHO_DELAY="${DNR_HTML_LITHO_DELAY:-0.2}"

AGENTIC_PILOT_MAX="${AGENTIC_PILOT_MAX:-400}"
AGENTIC_MODAL="${AGENTIC_MODAL:-1}"
AGENTIC_LOG_DIR="${AGENTIC_LOG_DIR:-$ROOT/.agentic-logs}"
mkdir -p "$AGENTIC_LOG_DIR"

if [[ "$AGENTIC_MODAL" == "1" ]]; then
  export DNR_FILL_MODAL_HTML=1
  export DNR_MODAL_HTML_UNLIMITED=1
fi

if [[ ! -f "$ROOT/dnr_report_html_lithology.py" ]]; then
  echo "ERROR: missing dnr_report_html_lithology.py. Run: git pull"
  exit 1
fi

python3 -c "from dnr_env_local import ensure_dnr_env_local_loaded; ensure_dnr_env_local_loaded()" 2>/dev/null || true

echo "== Agentic lithology pipeline =="
echo "  cwd: $ROOT"
echo "  DNR_OUT_DIR: $DNR_OUT_DIR"
echo "  DNR_HTTP_COOKIE: $([[ -n "${DNR_HTTP_COOKIE:-}" ]] && echo set || echo unset)"
echo "  AGENTIC_PILOT_MAX: $AGENTIC_PILOT_MAX"
echo "  DNR_HTML_LITHO_DELAY: $DNR_HTML_LITHO_DELAY"
echo "  AGENTIC_MODAL: $AGENTIC_MODAL"

timestamp="$(date +%Y%m%d-%H%M%S)"
PILOT_LOG_1="$AGENTIC_LOG_DIR/pilot-1-$timestamp.log"
PILOT_LOG_2="$AGENTIC_LOG_DIR/pilot-2-$timestamp.log"
FULL_LOG="$AGENTIC_LOG_DIR/full-$timestamp.log"

run_build_with_env() {
  local log_path="$1"
  shift
  (
    set -euo pipefail
    "$@" python3 rebuild_viewer_data.py
  ) 2>&1 | tee "$log_path"
}

extract_metrics_json() {
  local log_path="$1"
  python3 - "$log_path" <<'PY'
import json, re, sys
p = sys.argv[1]
text = open(p, encoding='utf-8', errors='replace').read()

def m1(rx, default=0):
    m = re.search(rx, text)
    return int(m.group(1).replace(',', '')) if m else default

def m2(rx):
    m = re.search(rx, text)
    if not m:
        return None
    return [int(x.replace(',', '')) for x in m.groups()]

backfill = m2(r"HTML backfill done:\s*log_table_from_html=([\d,]+)\s*drill_or_method_only=([\d,]+)\s*placeholder=([\d,]+)\s*capped_no_fetch=([\d,]+)")
fetchsum = m2(r"HTML lithology fetch summary:\s*new_HTTP=([\d,]+)\s*cache_hits=([\d,]+)")
obj = {
    "log_table": backfill[0] if backfill else 0,
    "meta_only": backfill[1] if backfill else 0,
    "placeholder": backfill[2] if backfill else 0,
    "capped": backfill[3] if backfill else 0,
    "new_http": fetchsum[0] if fetchsum else 0,
    "cache_hits": fetchsum[1] if fetchsum else 0,
    "source_html": m1(r"lithology_source after guarantee:\s*csv=[\d,]+\s*html=([\d,]+)\s*none=[\d,]+"),
}
print(json.dumps(obj))
PY
}

pilot_run() {
  local log_path="$1"
  local minimal_headers="$2"
  echo ""
  echo "== Pilot run (max=$AGENTIC_PILOT_MAX, refresh=1, minimal_headers=$minimal_headers) =="
  if [[ "$minimal_headers" == "1" ]]; then
    run_build_with_env "$log_path" env \
      DNR_FILL_LITHO_HTML=1 \
      DNR_HTML_LITHO_MAX="$AGENTIC_PILOT_MAX" \
      DNR_HTML_LITHO_REFRESH=1 \
      DNR_HTTP_MINIMAL_HEADERS=1 \
      DNR_HTML_LITHO_UNLIMITED= \
      DNR_FILL_MODAL_HTML=0
  else
    run_build_with_env "$log_path" env \
      DNR_FILL_LITHO_HTML=1 \
      DNR_HTML_LITHO_MAX="$AGENTIC_PILOT_MAX" \
      DNR_HTML_LITHO_REFRESH=1 \
      DNR_HTTP_MINIMAL_HEADERS= \
      DNR_HTML_LITHO_UNLIMITED= \
      DNR_FILL_MODAL_HTML=0
  fi
}

pilot_run "$PILOT_LOG_1" "0"
M1="$(extract_metrics_json "$PILOT_LOG_1")"
echo "Pilot metrics #1: $M1"

P1_LOG_TABLE="$(python3 -c "import json; print(json.loads('''$M1''')['log_table'])")"

if [[ "$P1_LOG_TABLE" -eq 0 ]]; then
  echo ""
  echo "Pilot #1 found 0 parsed Well Log tables. Retrying once with DNR_HTTP_MINIMAL_HEADERS=1..."
  pilot_run "$PILOT_LOG_2" "1"
  M2="$(extract_metrics_json "$PILOT_LOG_2")"
  echo "Pilot metrics #2: $M2"
  P2_LOG_TABLE="$(python3 -c "import json; print(json.loads('''$M2''')['log_table'])")"
  if [[ "$P2_LOG_TABLE" -eq 0 ]]; then
    echo ""
    echo "STOP: pilot still parsed 0 Well Log tables."
    echo "Most likely: DNR returned challenge/blocked HTML (cookie/session issue)."
    echo "Next steps:"
    echo "  1) Set DNR_HTTP_COOKIE in .env.local from secure.in.gov request headers"
    echo "  2) Optional: export DNR_HTML_DEBUG=1 then re-run this script"
    echo "Logs:"
    echo "  $PILOT_LOG_1"
    echo "  $PILOT_LOG_2"
    exit 2
  fi
fi

echo ""
echo "== Full statewide run (single final build) =="
run_build_with_env "$FULL_LOG" env \
  DNR_FILL_LITHO_HTML=1 \
  DNR_HTML_LITHO_UNLIMITED=1 \
  DNR_HTML_LITHO_MAX= \
  DNR_HTML_LITHO_REFRESH= \
  DNR_FILL_MODAL_HTML="$AGENTIC_MODAL"

M3="$(extract_metrics_json "$FULL_LOG")"
echo "Full-run metrics: $M3"

echo ""
echo "== Post-check =="
python3 verify_vein_g_production.py --all-chunks --chunk dnr_wells_chunk_0.csv.gz || true

echo ""
echo "Done. Logs:"
echo "  pilot #1: $PILOT_LOG_1"
[[ -f "$PILOT_LOG_2" ]] && echo "  pilot #2: $PILOT_LOG_2"
echo "  full:     $FULL_LOG"
