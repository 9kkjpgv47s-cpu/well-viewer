#!/usr/bin/env python3
"""
1) Run chunking (creates dnr_wells_chunk_0.csv.gz, chunk_1, ...).
2) Print one terminal command per chunk so you can upload each file.

Usage:
  python3 chunk_and_upload_commands.py [input.csv]

Copy-paste the commands one at a time into your terminal. Set BUCKET (and
R2_ENDPOINT for Cloudflare R2) first.
"""
import glob
import os
import subprocess
import sys

INPUT_FILE = "dnr_wells_full.csv"
CHUNK_GLOB = "dnr_wells_chunk_*.csv.gz"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    os.chdir(SCRIPT_DIR)
    input_path = sys.argv[1] if len(sys.argv) > 1 else INPUT_FILE

    # 1) Ensure chunk files exist
    chunks = sorted(glob.glob(CHUNK_GLOB))
    if not chunks:
        if not os.path.exists(input_path):
            print(f"Missing {input_path}. Run fetch_dnr_wells.py first.", file=sys.stderr)
            sys.exit(1)
        print("Running chunking first...\n")
        subprocess.run([sys.executable, "chunk_dnr_csv.py", input_path], check=True)
        chunks = sorted(glob.glob(CHUNK_GLOB))

    if not chunks:
        print("No chunk files produced.", file=sys.stderr)
        sys.exit(1)

    # 2) Print one upload command per chunk
    print("\n" + "=" * 72)
    print("STEP 1 — Set your bucket (run once in the terminal)")
    print("=" * 72)
    print("\nexport BUCKET=your-bucket-name\n")
    print("If you use Cloudflare R2, also run (replace YOUR_ACCOUNT_ID):")
    print('export R2_ENDPOINT="https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com"\n')

    print("=" * 72)
    print("STEP 2 — Upload each chunk (copy-paste ONE command at a time)")
    print("=" * 72)
    print("\n--- AWS S3 (use these if you use S3) ---\n")
    for f in chunks:
        if os.path.isfile(f):
            print(f'aws s3 cp "{f}" s3://$BUCKET/')

    print("\n--- Cloudflare R2 (use these if you use R2) ---\n")
    for f in chunks:
        if os.path.isfile(f):
            print(f'aws s3 cp "{f}" s3://$BUCKET/ --endpoint-url "$R2_ENDPOINT"')

    print("\n" + "=" * 72)
    print("After uploading, set DNR_CHUNK_BASE_URL in the app to your bucket public URL.")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    main()
