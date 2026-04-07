#!/usr/bin/env python3
"""
Scan statewide_wells_chunk_*.csv.gz and report how many rows have non-empty lithology_json.
Exit 1 if zero (map **g** labels cannot work from chunks alone).

Usage:
  python3 verify_chunks_lithology.py
  python3 verify_chunks_lithology.py /path/to/repo
"""
import csv
import glob
import gzip
import os
import sys


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    pattern = os.path.join(root, "statewide_wells_chunk_*.csv.gz")
    files = sorted(glob.glob(pattern))
    if not files:
        print("No statewide_wells_chunk_*.csv.gz found in", root)
        sys.exit(1)

    total_rows = 0
    with_litho = 0
    for path in files:
        r = 0
        wl = 0
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                r += 1
                lj = (row.get("lithology_json") or "").strip()
                if lj and lj != "[]":
                    wl += 1
        total_rows += r
        with_litho += wl
        print(f"{os.path.basename(path)}: {r:,} rows, {wl:,} with lithology_json")

    print(f"\nTOTAL: {total_rows:,} rows, {with_litho:,} with lithology_json")
    if with_litho == 0:
        print(
            "\nFAIL: lithology_json is empty everywhere — rebuild chunks with lithology:\n"
            "  1) Obtain DNR litho.txt (database download).\n"
            "  2) Place litho.txt next to dnr_wells_full.csv (or set DNR_LITHO_TXT).\n"
            "  3) python3 build_statewide_data.py\n"
            "  4) python3 verify_chunks_lithology.py\n"
            "Then deploy the new statewide_wells_chunk_*.csv.gz files."
        )
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
