#!/usr/bin/env python3
"""
Serve DNR_Well_Viewer_Full_Demo locally and drive the real viewer in headless Chromium.

  pip install playwright
  python3 -m playwright install chromium
  python3 scripts/viewer_probe.py

Open in Cursor Simple Browser or any browser (same machine):

  http://127.0.0.1:PORT/index.html?cj_probe=1

Default --server-only port is 8767 (avoids clashing with other local servers). Override: --port N.
PORT is printed on stdout. Query ?cj_probe=1 loads fixtures/chunks/dnr_wells_chunk_0.csv.gz only.

In DevTools console on any page load: __cjProbeGLabels(5000)
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import socket
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Default when --server-only and --port omitted (8765/8766 often already in use locally).
DEFAULT_SERVER_ONLY_PORT = 8767
FIXTURE_CSV = """refno,id,lat,lon,depth,county,aquifer,vein_size_ft,depth_bedrock,loc_type,owner
991001,DNR-991001,39.6000,-86.5000,120,Hendricks,Unconsolidated,35,,Field Located,PROBE-G-OK
991002,DNR-991002,39.6001,-86.5001,120,Hendricks,Unconsolidated,118,,Field Located,PROBE-G-THICK
991003,DNR-991003,39.6002,-86.5002,200,Marion,Limestone,,45,Field Located,PROBE-R-OK
991004,DNR-991004,39.6003,-86.5003,100,Hendricks,Unconsolidated,,,Field Located,PROBE-NO-VEIN
991005,DNR-991005,39.6004,-86.5004,100,Hendricks,Unconsolidated,100,,Field Located,PROBE-G-EQ-DEPTH
"""


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    _, port = s.getsockname()
    s.close()
    return port


def write_fixture_gzip() -> Path:
    d = ROOT / "fixtures" / "chunks"
    d.mkdir(parents=True, exist_ok=True)
    csv_path = d / "dnr_wells_chunk_0.csv"
    gz_path = d / "dnr_wells_chunk_0.csv.gz"
    if not csv_path.is_file():
        csv_path.write_text(FIXTURE_CSV, encoding="utf-8")
    with open(csv_path, "rb") as raw:
        data = raw.read()
    with gzip.open(gz_path, "wb") as gz:
        gz.write(data)
    return gz_path


def run_server_only(port: int) -> None:
    """Serve the repo root; open /index.html?cj_probe=1 in Cursor Simple Browser or Chrome."""
    write_fixture_gzip()
    os.chdir(ROOT)
    handler = type(
        "H",
        (SimpleHTTPRequestHandler,),
        {"extensions_map": {**SimpleHTTPRequestHandler.extensions_map, ".gz": "application/gzip"}},
    )
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{port}/index.html?cj_probe=1&cj_dump=1"
    print(f"Serving {ROOT}", flush=True)
    print(f"Open: {url}", flush=True)
    print("In DevTools console: __cjProbeGLabels(5000)", flush=True)
    print("Ctrl+C to stop.", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
    finally:
        httpd.server_close()


def run_probe(port: int, headless: bool, pause_before_exit: bool) -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Missing playwright. Run:\n  pip install playwright\n  python3 -m playwright install chromium",
            file=sys.stderr,
        )
        return 2

    os.chdir(ROOT)
    handler = type(
        "H",
        (SimpleHTTPRequestHandler,),
        {"extensions_map": {**SimpleHTTPRequestHandler.extensions_map, ".gz": "application/gzip"}},
    )

    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    time.sleep(0.2)

    url = f"http://127.0.0.1:{port}/index.html?cj_probe=1&cj_dump=1"
    print(f"Viewer (fixture probe): {url}", flush=True)
    print("Console API: __cjProbeGLabels(5000)", flush=True)

    exit_code = 0
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page()
            lines: list[str] = []

            def on_console(msg) -> None:
                try:
                    lines.append(f"[browser:{msg.type}] {msg.text}")
                except Exception:
                    pass

            page.on("console", on_console)
            page.goto(url, wait_until="load", timeout=120_000)
            page.wait_for_function(
                """() => window.wells && window.wells.length >= 20
                && window.wells.some(function(w) { return String(w.id) === 'DNR-991020'; })
                && typeof window.__cjProbeGLabels === 'function'
                && window.__cjGLabelFixtureReport && window.__cjGLabelFixtureReport.checked >= 20""",
                timeout=120_000,
            )
            time.sleep(0.5)
            data = page.evaluate("() => window.__cjProbeGLabels(5000)")
            print(json.dumps(data, indent=2), flush=True)
            rep = page.evaluate("() => window.__cjGLabelFixtureReport || {}")
            print(json.dumps(rep, indent=2), flush=True)

            if "[C&J]" in "\n".join(lines):
                print("--- browser console (filtered) ---", flush=True)
                for ln in lines:
                    if "[C&J]" in ln or "chunk" in ln.lower():
                        print(ln, flush=True)

            g = data.get("g", 0)
            r = data.get("r", 0)
            none = data.get("none", 0)
            if not rep.get("ok"):
                print(
                    f"ASSERT FAIL: __cjGLabelFixtureReport ok=false mismatches={rep.get('mismatches')!r}",
                    file=sys.stderr,
                )
                exit_code = 1
            elif rep.get("checked", 0) < 20:
                print(
                    f"ASSERT FAIL: expected 20 EXPECT: rows checked, got {rep.get('checked')!r}",
                    file=sys.stderr,
                )
                exit_code = 1
            elif g < 8 or r < 2 or none < 3:
                print(
                    f"ASSERT FAIL: sanity g>=8, r>=2, none>=3 (20-row fixture); got g={g} r={r} none={none}",
                    file=sys.stderr,
                )
                exit_code = 1
            else:
                print("OK: 20-row g-label fixtures + distribution sanity.", flush=True)

            if not headless and pause_before_exit:
                input("Press Enter to close the browser and stop the server…")
            browser.close()
    except Exception as e:
        print(f"PROBE ERROR: {e}", file=sys.stderr)
        exit_code = 1
    finally:
        httpd.shutdown()

    return exit_code


def main() -> None:
    ap = argparse.ArgumentParser(description="Serve viewer + headless probe g/r labels (fixture chunk).")
    ap.add_argument("--port", type=int, default=0, help="HTTP port (0 = auto for --probe)")
    ap.add_argument(
        "--server-only",
        action="store_true",
        help="Only start http.server (no Playwright). Use Cursor Simple Browser on the printed URL.",
    )
    ap.add_argument("--headed", action="store_true", help="Show Chromium window (requires Playwright)")
    ap.add_argument(
        "--keep",
        action="store_true",
        help="With --headed: wait for Enter before closing (inspect the map)",
    )
    args = ap.parse_args()

    if args.server_only:
        port = args.port or DEFAULT_SERVER_ONLY_PORT
        run_server_only(port)
        raise SystemExit(0)

    write_fixture_gzip()
    port = args.port or _free_port()
    code = run_probe(port, headless=not args.headed, pause_before_exit=args.headed and args.keep)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
