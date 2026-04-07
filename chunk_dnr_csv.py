#!/usr/bin/env python3
"""
Split a large DNR wells CSV into gzipped chunk files. Rows are SHUFFLED before
chunking so each chunk has wells from all over Indiana (not just south or north).
No data loss — the viewer fetches and merges all chunks.

**Production / accurate g-labels:** run `python3 rebuild_viewer_data.py` instead.
That merges WellLogs, adds vein_size_ft / lithology_json, and writes dnr_wells_chunk_*.csv.gz.
This script only splits columns already present in the input CSV.

Usage:
  python3 chunk_dnr_csv.py [input.csv]
Default input: dnr_wells_full.csv or dnr_wells_full.csv.gz (after fetch or from git)

Output: dnr_wells_chunk_0.csv.gz … (row count per MAX_ROWS_PER_CHUNK)
"""
import csv
import gzip
import os
import random
import sys

from dnr_csv_input import open_dnr_wells_csv_for_read, resolve_dnr_full_wells_csv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = "dnr_wells_full.csv"
CHUNK_PREFIX = "dnr_wells_chunk"
# Split into 8 chunks (~52k rows each); each .gz stays under 100 MB
MAX_ROWS_PER_CHUNK = 52_000
# Fixed seed so re-runs give same chunks (reproducible)
SHUFFLE_SEED = 42


def main():
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
        if not os.path.isfile(input_path):
            print(f"Missing {input_path}.", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            input_path = resolve_dnr_full_wells_csv(SCRIPT_DIR, None)
        except FileNotFoundError as e:
            print(f"{e} Run fetch_dnr_wells.py or pass a CSV path.", file=sys.stderr)
            sys.exit(1)

    print(f"Reading {input_path}...")
    with open_dnr_wells_csv_for_read(input_path) as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if not fieldnames:
            print("No header in CSV.", file=sys.stderr)
            sys.exit(1)
        rows = list(reader)

    total_rows = len(rows)
    print(f"Loaded {total_rows:,} rows. Shuffling so each chunk has statewide coverage...")
    random.seed(SHUFFLE_SEED)
    random.shuffle(rows)

    print(f"Writing gzipped chunks ({MAX_ROWS_PER_CHUNK:,} rows per chunk)...\n")
    chunk_index = 0
    start = 0
    while start < total_rows:
        end = min(start + MAX_ROWS_PER_CHUNK, total_rows)
        chunk_rows = rows[start:end]
        current_path = f"{CHUNK_PREFIX}_{chunk_index}.csv"
        with open(current_path, "w", newline="", encoding="utf-8") as out:
            writer = csv.DictWriter(out, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(chunk_rows)
        gz_path = f"{CHUNK_PREFIX}_{chunk_index}.csv.gz"
        with open(current_path, "rb") as csv_in:
            with gzip.open(gz_path, "wb") as gz_out:
                gz_out.writelines(csv_in)
        os.remove(current_path)
        size_mb = os.path.getsize(gz_path) / (1024 * 1024)
        print(f"  {gz_path}: {len(chunk_rows):,} rows, {size_mb:.1f} MB")
        chunk_index += 1
        start = end

    print(f"\nTotal: {total_rows:,} rows in {chunk_index} chunk(s).")
    print("Deploy all dnr_wells_chunk_*.csv.gz files. The app will load and merge them.")
    print("Vercel: keep dnr_wells_chunk_*.csv.gz in repo root next to index.html (same as statewide chunks).")


if __name__ == "__main__":
    main()
