#!/usr/bin/env bash
# One local rebuild for the viewer: merged chunks with vein_size_ft + aquifer + lithology_json.
# Output: dnr_wells_chunk_*.csv.gz in this directory (default). Deploy by placing those files next to index.html.
set -euo pipefail
cd "$(dirname "$0")"
python3 rebuild_viewer_data.py "$@"
