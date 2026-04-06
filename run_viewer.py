#!/usr/bin/env python3
"""
Single local dev entrypoint — no manual ports, no copying chunk files for the sanity check.

  cd DNR_Well_Viewer_Full_Demo
  python3 run_viewer.py

- Picks a free port on 127.0.0.1
- Writes the tiny probe chunk (fixtures/chunks/dnr_wells_chunk_0.csv.gz)
- Serves this folder
- Opens your default browser

Default page: fixture probe + on-screen JSON (?cj_probe=1&cj_dump=1).

  python3 run_viewer.py --full

Opens plain index.html (uses real dnr_wells_chunk_*.csv.gz next to index.html if you have them).

Stop: Ctrl+C
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import socket
import sys
import threading
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load_viewer_probe():
    path = ROOT / "scripts" / "viewer_probe.py"
    spec = importlib.util.spec_from_file_location("viewer_probe", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pick_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    _, port = s.getsockname()
    s.close()
    return int(port)


def main() -> None:
    ap = argparse.ArgumentParser(description="Serve viewer and open browser (one command).")
    ap.add_argument(
        "--full",
        action="store_true",
        help="Open full viewer only (no probe query). Uses your real .csv.gz chunks if present.",
    )
    args = ap.parse_args()

    vp = _load_viewer_probe()
    vp.write_fixture_gzip()

    os.chdir(ROOT)
    handler = type(
        "CJViewerHandler",
        (SimpleHTTPRequestHandler,),
        {"extensions_map": {**SimpleHTTPRequestHandler.extensions_map, ".gz": "application/gzip"}},
    )
    port = _pick_free_port()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)

    if args.full:
        url = f"http://127.0.0.1:{port}/index.html"
    else:
        url = f"http://127.0.0.1:{port}/index.html?cj_probe=1&cj_dump=1"

    def _open_browser() -> None:
        time.sleep(0.25)
        webbrowser.open(url)

    threading.Thread(target=_open_browser, daemon=True).start()

    print(f"Serving: {ROOT}", flush=True)
    print(f"URL:     {url}", flush=True)
    print("Browser should open automatically. Ctrl+C to stop.", flush=True)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
    finally:
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    main()
