#!/usr/bin/env python3
"""
Canonical data rebuild for the well viewer: merge WellLogs + enrich vein columns + gzip chunks.

Output files match the default viewer setting DNR_CHUNK_PREFIX = 'dnr_wells_chunk_'.
Run from the repo root after placing logs under well_logs_csv/, or set DNR_LOGS_CSV_PATHS to use only those files.
Before a long HTML backfill, run ./dnr_reliability_preflight.sh (or python3 debug_dnr_html.py --preflight).

Usage:
  python3 rebuild_viewer_data.py
  python3 rebuild_viewer_data.py --skip-build   # only verify existing dnr_wells_chunk_0.csv.gz
"""
from __future__ import annotations

import argparse
import gzip
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHUNK_BASE = os.environ.get("DNR_CHUNK_FILE_PREFIX", "dnr_wells_chunk").strip().rstrip("_")
REQUIRED_HEADER_TOKENS = (
    "refno",
    "lat",
    "lon",
    "aquifer",
    "vein_size_ft",
    "lithology_json",
)


def verify_chunk0(out_dir: str) -> None:
    path = os.path.join(out_dir, f"{CHUNK_BASE}_0.csv.gz")
    if not os.path.isfile(path):
        print(f"ERROR: missing {path}", file=sys.stderr)
        sys.exit(1)
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        header = f.readline().lower()
    for tok in REQUIRED_HEADER_TOKENS:
        if tok not in header:
            print(f"ERROR: {path} header missing required column {tok!r}", file=sys.stderr)
            sys.exit(1)
    # Expect at least one more data row
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    if len(lines) < 2:
        print(f"ERROR: {path} has no data rows", file=sys.stderr)
        sys.exit(1)
    print(f"OK: {os.path.basename(path)} header + {len(lines) - 1:,} data lines")


def main() -> None:
    ap = argparse.ArgumentParser(description="Rebuild gzipped well chunks for the viewer.")
    ap.add_argument(
        "--skip-build",
        action="store_true",
        help="Only verify chunk 0; do not run build_statewide_data.py",
    )
    ap.add_argument(
        "--out-dir",
        default=os.environ.get("DNR_OUT_DIR", SCRIPT_DIR),
        help="Directory for CSV source + chunk output (default: repo root)",
    )
    args = ap.parse_args()
    out_dir = os.path.abspath(args.out_dir)

    if not args.skip_build:
        script = os.path.join(SCRIPT_DIR, "build_statewide_data.py")
        env = os.environ.copy()
        env["DNR_OUT_DIR"] = out_dir
        r = subprocess.run([sys.executable, script], cwd=SCRIPT_DIR, env=env)
        if r.returncode != 0:
            sys.exit(r.returncode)

    verify_chunk0(out_dir)
    n_extra = 0
    chunk_re = re.compile(rf"^{re.escape(CHUNK_BASE)}_(\d+)\.csv\.gz$")
    for fn in os.listdir(out_dir):
        m = chunk_re.match(fn)
        if m:
            n_extra = max(n_extra, int(m.group(1)) + 1)
    if n_extra:
        print(f"Deploy all {CHUNK_BASE}_0.csv.gz … {CHUNK_BASE}_{n_extra - 1}.csv.gz with index.html.")
        print(
            f"Viewer loads exactly {n_extra} chunk file(s). If that is not 8, set window.CJ_DNR_CHUNK_COUNT = {n_extra} "
            "before load, or change the default `dnrChunkExpected` in index.html → loadFullDnrDataset."
        )


if __name__ == "__main__":
    main()
