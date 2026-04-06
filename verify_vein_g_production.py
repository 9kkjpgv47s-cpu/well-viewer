#!/usr/bin/env python3
"""
Verify production g-label inputs in gzipped viewer chunks (after rebuild_viewer_data.py).

Checks:
  • Chunk 0 exists and header includes vein_size_ft (same tokens as rebuild_viewer_data.verify_chunk0).
  • Rows with positive vein_size_ft: value is parseable, optionally vs completed depth for sanity warnings.

Does not import the HTML viewer — encodes the same production rule: map g should use vein_size_ft when present.

Usage (from repo root):
  python3 verify_vein_g_production.py
  python3 verify_vein_g_production.py --chunk dnr_wells_chunk_0.csv.gz --max-rows 50000
  python3 verify_vein_g_production.py --all-chunks --chunk dnr_wells_chunk_0.csv.gz   # all 9 files, full rows
"""
from __future__ import annotations

import argparse
import csv
import gzip
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CHUNK = os.path.join(SCRIPT_DIR, "dnr_wells_chunk_0.csv.gz")
CHUNK_GLOB_RE = re.compile(r"dnr_wells_chunk_(\d+)\.csv\.gz$", re.I)


def g_vein_plausible_vs_depth(g: float, depth: float | None) -> bool:
    """Same thresholds as viewer gThicknessIsPlausibleVsCompletedDepth (reject g ≈ completed depth)."""
    if g is None or g <= 0:
        return False
    if depth is None or depth <= 0:
        return True
    if g > depth + 0.5:
        return False
    if g >= depth - 1.5:
        return False
    if depth >= 15 and g / depth >= 0.92:
        return False
    return True


def safe_float(s: str) -> float | None:
    s = (s or "").strip().replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _discover_chunk_paths(scan_dir: str) -> list[str]:
    out: list[tuple[int, str]] = []
    if not os.path.isdir(scan_dir):
        return []
    for fn in os.listdir(scan_dir):
        m = CHUNK_GLOB_RE.search(fn)
        if not m:
            continue
        out.append((int(m.group(1)), os.path.join(scan_dir, fn)))
    out.sort(key=lambda x: x[0])
    return [p for _, p in out]


def _scan_rows(
    path: str,
    limit: int,
) -> tuple[int, int, int, int, int, int, int]:
    """Returns rows, vein_pos, rock_pos, gravel_pos, vein_warn_depth, vein_implausible_depth, litho_substantial."""
    n_rows = 0
    n_vein_pos = 0
    n_rock_pos = 0
    n_gravel_col_pos = 0
    n_vein_warn_depth = 0
    n_vein_implausible = 0
    n_litho_real = 0
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            n_rows += 1
            if limit and n_rows > limit:
                break
            vs = safe_float(row.get("vein_size_ft") or "")
            dep = safe_float(row.get("depth") or "")
            if vs is not None and vs > 0:
                n_vein_pos += 1
                if dep is not None and dep > 0 and vs > dep + 0.5:
                    n_vein_warn_depth += 1
                if not g_vein_plausible_vs_depth(vs, dep):
                    n_vein_implausible += 1
            rs = safe_float(row.get("rock_start_ft") or "")
            if rs is not None and rs > 0:
                n_rock_pos += 1
            gt = safe_float(row.get("gravel_thickness_ft") or "")
            if gt is not None and gt > 0:
                n_gravel_col_pos += 1
            lj = (row.get("lithology_json") or "").strip()
            if len(lj) > 80 and "no digitized" not in lj.lower():
                n_litho_real += 1
    return (
        n_rows,
        n_vein_pos,
        n_rock_pos,
        n_gravel_col_pos,
        n_vein_warn_depth,
        n_vein_implausible,
        n_litho_real,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Verify vein_size_ft in viewer chunks.")
    ap.add_argument("--chunk", default=DEFAULT_CHUNK, help="Path to dnr_wells_chunk_0.csv.gz")
    ap.add_argument(
        "--all-chunks",
        action="store_true",
        help="Scan every dnr_wells_chunk_*.csv.gz in the same directory (full statewide totals)",
    )
    ap.add_argument(
        "--max-rows",
        type=int,
        default=0,
        help="Max data rows per file (0 = all). Ignored with --all-chunks (always all rows).",
    )
    args = ap.parse_args()
    path = os.path.abspath(args.chunk)

    if args.all_chunks:
        scan_dir = os.path.dirname(path) if os.path.isfile(path) else path
        if not os.path.isdir(scan_dir):
            scan_dir = SCRIPT_DIR
        chunk_paths = _discover_chunk_paths(scan_dir)
        if not chunk_paths:
            print(f"SKIP: no dnr_wells_chunk_*.csv.gz in {scan_dir}", file=sys.stderr)
            sys.exit(0)
        first = chunk_paths[0]
    else:
        chunk_paths = [path]
        first = path

    if not os.path.isfile(first):
        print(
            f"SKIP: no chunk at {first}\n"
            "  Build chunks with: python3 rebuild_viewer_data.py\n"
            "  Then re-run this script to verify production vein_size_ft coverage.",
            file=sys.stderr,
        )
        sys.exit(0)

    required = ("refno", "lat", "lon", "vein_size_ft", "lithology_json")
    with gzip.open(first, "rt", encoding="utf-8", errors="replace") as f:
        header_line = f.readline().lower()
    for tok in required:
        if tok not in header_line:
            print(f"FAIL: header missing {tok!r} in {first}", file=sys.stderr)
            sys.exit(1)

    limit = 0 if args.all_chunks else args.max_rows
    tot_rows = tot_vein = tot_rock = tot_gravel = tot_warn = tot_impl = tot_litho = 0
    for cp in chunk_paths:
        r, v, rk, g, w, impl, lith = _scan_rows(cp, limit)
        tot_rows += r
        tot_vein += v
        tot_rock += rk
        tot_gravel += g
        tot_warn += w
        tot_impl += impl
        tot_litho += lith

    if args.all_chunks:
        print(f"OK: {len(chunk_paths)} chunk file(s) in {os.path.dirname(first)}")
        for cp in chunk_paths:
            print(f"  • {os.path.basename(cp)}")
    else:
        print(f"OK: {os.path.basename(first)}")

    pct = (100.0 * tot_vein / tot_rows) if tot_rows else 0.0
    pct_lith = (100.0 * tot_litho / tot_rows) if tot_rows else 0.0
    print(f"  rows scanned: {tot_rows:,}")
    print(f"  vein_size_ft > 0: {tot_vein:,} ({pct:.2f}% of rows)")
    print(
        f"  rock_start_ft > 0: {tot_rock:,}  |  gravel_thickness_ft > 0: {tot_gravel:,} "
        "(GravelVeinCorrector CSV tags)"
    )
    print(
        f"  lithology_json looks non-placeholder (heuristic): {tot_litho:,} ({pct_lith:.2f}% of rows)"
    )
    if tot_warn:
        print(
            f"  WARN: {tot_warn} row(s) have vein_size_ft > depth+0.5 ft (spot-check data / typos)",
            file=sys.stderr,
        )
    if tot_impl:
        print(
            f"  NOTE: {tot_impl} row(s) fail strict litho-style g plausibility (near-TD / high g/depth). "
            "Viewer still accepts baked vein_size_ft when g < completed depth (pipeline trust).",
            file=sys.stderr,
        )
    if tot_rows and tot_vein == 0 and tot_gravel == 0 and tot_rock == 0:
        if args.all_chunks:
            print(
                "WARN: no positive vein/rock columns in any scanned chunk — check build_statewide_data / registry bake.",
                file=sys.stderr,
            )
        else:
            print(
                "WARN: chunk 0 has no vein_size_ft — wells with g may sit in later chunks (CSV row order). "
                "Re-run with: python3 verify_vein_g_production.py --all-chunks --chunk "
                + repr(first),
                file=sys.stderr,
            )
    elif tot_rows and tot_vein == 0 and (tot_gravel > 0 or tot_rock > 0):
        print(
            "NOTE: vein_size_ft is often 0 when GravelVeinCorrector finds no screen-overlap gravel vein; "
            "gravel_thickness_ft / lithology may still drive g.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
