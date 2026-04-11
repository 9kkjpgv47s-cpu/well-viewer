#!/usr/bin/env bash
# Run lithology + vein/g checks + Playwright tests (no inline # comments — those break copy-paste).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== Node lithology aggregate tests =="
node tests/run_litho_aggregate_tests.cjs

echo ""
echo "== verify_vein_g_production (all deployed chunks) =="
python3 verify_vein_g_production.py --all-chunks --chunk dnr_wells_chunk_0.csv.gz

echo ""
echo "== Playwright browser install (project-local .pw-browsers; idempotent) =="
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$ROOT/.pw-browsers}"
"$ROOT/.venv/bin/playwright" install chromium

echo ""
echo "== Playwright lithology E2E =="
"$ROOT/.venv/bin/python" tests/test_litho_aggregate_playwright.py

echo ""
echo "== Headless g-label fixture probe =="
"$ROOT/.venv/bin/python" scripts/viewer_probe.py --port 0

echo ""
echo "All test steps finished OK."
