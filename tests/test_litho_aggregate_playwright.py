#!/usr/bin/env python3
"""
End-to-end validation of lithology sum-all sand/gravel/water-bearing logic in index.html.

Requires: playwright + chromium (from repo .venv):
  cd DNR_Well_Viewer_Full_Demo && .venv/bin/pip install -r requirements-probe.txt
  .venv/bin/playwright install chromium

Run:
  .venv/bin/python tests/test_litho_aggregate_playwright.py

No browser / no CDN (CI-friendly) — same scenarios as the Node mirror:
  node tests/run_litho_aggregate_tests.cjs
"""
from __future__ import annotations

import http.server
import socketserver
import threading
import time
import urllib.error
import urllib.request
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Project-local browser dir (avoids relying on ~/Library/Caches; add to CI: playwright install chromium).
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT / ".pw-browsers"))


def _handler_factory():
    class _Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT), **kwargs)

        def log_message(self, format, *args):
            pass

    return _Handler


def _wait_http_ready(url: str, timeout_s: float = 30.0) -> None:
    deadline = time.time() + timeout_s
    last_err = None
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except (urllib.error.URLError, OSError) as e:
            last_err = e
            time.sleep(0.15)
    raise RuntimeError(f"Server not ready: {url} last_err={last_err}")


def main() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise SystemExit(
            "Install playwright: .venv/bin/pip install -r requirements-probe.txt && .venv/bin/playwright install chromium"
        ) from e

    handler = _handler_factory()
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
        httpd.allow_reuse_address = True
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{port}/"
        _wait_http_ready(base)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            page.goto(f"{base}index.html", wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(2000)

            results = page.evaluate(
                """
() => {
  const out = { errors: [], passed: [] };
  function ok(name) { out.passed.push(name); }
  function fail(name, msg) { out.errors.push(name + ': ' + msg); }

  if (typeof cjSumAllSandGravelWaterBearingIntervalsFt !== 'function')
    fail('globals', 'cjSumAllSandGravelWaterBearingIntervalsFt missing');
  if (typeof cjListSandGravelAquiferLayers !== 'function')
    fail('globals', 'cjListSandGravelAquiferLayers missing');
  if (typeof cjScanRowStringsForSandGravelKeywords !== 'function')
    fail('globals', 'cjScanRowStringsForSandGravelKeywords missing');
  if (typeof getGravelVeinDisplayFt !== 'function')
    fail('globals', 'getGravelVeinDisplayFt missing');
  if (out.errors.length) return out;

  const uid = () => 'pw-' + Math.random().toString(36).slice(2, 11);

  // Multi-interval: clay skip, S&G +15, limestone skip, SA&GR +15 => 30
  const w1 = {
    id: uid(),
    depth: '100',
    lithology_json: JSON.stringify([
      { top: 0, bottom: 10, formation: 'clay' },
      { top: 10, bottom: 25, formation: 'sand and gravel' },
      { top: 25, bottom: 40, formation: 'LIMESTONE' },
      { top: 40, bottom: 55, formation: 'SA & GR water bearing' },
    ]),
  };
  const s1 = cjSumAllSandGravelWaterBearingIntervalsFt(w1);
  if (s1 !== 30) fail('sum_multi', 'expected 30 got ' + s1);
  else ok('sum_multi_intervals_30ft');

  const layers1 = cjListSandGravelAquiferLayers(w1);
  if (layers1.length !== 2) fail('list_multi', 'expected 2 layers got ' + layers1.length);
  else ok('list_two_matching_intervals');

  // Depth clip: completed depth 50, sand 0-80 => count 50 ft only
  const w2 = { id: uid(), depth: '50', lithology_json: JSON.stringify([{ top: 0, bottom: 80, formation: 'coarse sand' }]) };
  const s2 = cjSumAllSandGravelWaterBearingIntervalsFt(w2);
  if (s2 !== 50) fail('depth_clip', 'expected 50 got ' + s2);
  else ok('depth_clip_to_completed');

  // Placeholder row skipped
  const w3 = {
    id: uid(),
    depth: '40',
    lithology_json: JSON.stringify([
      { top: 0, bottom: 40, formation: 'No digitized table for this well' },
    ]),
  };
  const s3 = cjSumAllSandGravelWaterBearingIntervalsFt(w3);
  if (s3 !== null) fail('placeholder', 'expected null got ' + s3);
  else ok('skip_placeholder_formation');

  // CSV keyword scan (no thickness)
  const w4 = { id: uid(), depth: '20', aquifer: 'Unconsolidated sand and gravel aquifer', county: 'Test' };
  const hits = cjScanRowStringsForSandGravelKeywords(w4);
  if (!hits.some(function (h) { return h.field === 'aquifer'; }))
    fail('keyword_scan', 'expected aquifer hit, got ' + JSON.stringify(hits));
  else ok('csv_keyword_aquifer');

  const w5 = {
    id: uid(),
    depth: '100',
    lithology_json: JSON.stringify([
      { top: 5, bottom: 20, formation: 'gravel' },
      { top: 25, bottom: 35, formation: 'pea gravel' },
    ]),
  };
  const g5 = getGravelVeinDisplayFt(w5);
  if (g5 !== 25) fail('g_display', 'expected 25 (10+15) got ' + g5);
  else ok('getGravelVeinDisplayFt_sum_all_25');

  const w6 = {
    id: uid(),
    depth: '100',
    vein_size_ft: '99',
    screen_length: '5',
    lithology_json: JSON.stringify([{ top: 0, bottom: 12, formation: 'gravel' }]),
  };
  const g6 = getGravelVeinDisplayFt(w6);
  if (g6 !== 12) fail('ignore_csv_vein_screen', 'expected lithology 12 not vein/screen, got ' + g6);
  else ok('g_ignores_vein_size_ft_and_screen_length');

  return out;
}
"""
            )

            browser.close()
        httpd.shutdown()

    errors = results.get("errors") or []
    passed = results.get("passed") or []
    print("Passed ({}): {}".format(len(passed), ", ".join(passed)))
    if errors:
        print("FAILED ({}):".format(len(errors)))
        for e in errors:
            print("  -", e)
        raise SystemExit(1)
    print("All lithology aggregate checks OK.")


if __name__ == "__main__":
    main()
