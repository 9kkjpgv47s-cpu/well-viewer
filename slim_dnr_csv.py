#!/usr/bin/env python3
"""
Read dnr_wells_full.csv or dnr_wells_full.csv.gz and write a slim CSV (only columns the viewer needs)
so the file fits under Vercel's 100 MB limit. Also writes a gzipped version
for deployment (dnr_wells_slim.csv.gz — use this on Vercel).

Run after fetch_dnr_wells.py:
  python3 slim_dnr_csv.py
"""
import csv
import gzip
import os
import sys

from dnr_csv_input import open_dnr_wells_csv_for_read, resolve_dnr_full_wells_csv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = "dnr_wells_full.csv"
OUTPUT_CSV = "dnr_wells_slim.csv"
OUTPUT_GZ = "dnr_wells_slim.csv.gz"

# Only columns the map/detail view needs (keeps file small)
SLIM_COLUMNS = ["refno", "lat", "lon", "depth", "county", "owner", "report", "loc_type"]


def main():
    try:
        input_path = resolve_dnr_full_wells_csv(SCRIPT_DIR, None)
    except FileNotFoundError as e:
        print(f"{e}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading {input_path}...")
    rows = []
    with open_dnr_wells_csv_for_read(input_path) as f:
        r = csv.DictReader(f)
        for row in r:
            refno = row.get("refno", "")
            slim = {k: row.get(k, "") for k in SLIM_COLUMNS}
            slim["id"] = f"DNR-{refno}" if refno else ""
            rows.append(slim)

    print(f"Writing {len(rows):,} rows to {OUTPUT_CSV}...")
    fieldnames = ["id"] + SLIM_COLUMNS
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    size_csv = os.path.getsize(OUTPUT_CSV)
    print(f"  {OUTPUT_CSV}: {size_csv / (1024*1024):.1f} MB")

    print(f"Writing {OUTPUT_GZ} (for Vercel deploy)...")
    with open(OUTPUT_CSV, "rb") as f_in:
        with gzip.open(OUTPUT_GZ, "wb") as f_out:
            f_out.writelines(f_in)

    size_gz = os.path.getsize(OUTPUT_GZ)
    print(f"  {OUTPUT_GZ}: {size_gz / (1024*1024):.1f} MB")

    if size_gz > 100 * 1024 * 1024:
        print("\nWarning: gzipped file is still over 100 MB. Vercel may reject it.", file=sys.stderr)
    else:
        print("\nDeploy dnr_wells_slim.csv.gz to your project. The app will load it automatically.")


if __name__ == "__main__":
    main()
