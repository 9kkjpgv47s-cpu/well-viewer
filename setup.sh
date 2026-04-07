#!/usr/bin/env bash
# One entry point after clone: optional Git LFS + reminder that builds need no decompress.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "DNR Well Viewer — quick setup"
echo "--------------------------------"

if [[ "${INSTALL_GIT_LFS:-}" == "1" ]] && [[ "$(uname -s)" == "Darwin" ]]; then
  bash "$ROOT/scripts/install_git_lfs_mac.sh"
elif git lfs version &>/dev/null; then
  git lfs install
  echo "Git LFS: $(git lfs version | head -1)"
else
  echo "Git LFS: not installed (optional). For Mac without Homebrew:"
  echo "  INSTALL_GIT_LFS=1 ./setup.sh"
fi

echo ""
if [[ -f "$ROOT/dnr_wells_full.csv.gz" ]]; then
  echo "Full wells data: dnr_wells_full.csv.gz (OK — Python reads this directly)"
elif [[ -f "$ROOT/dnr_wells_full.csv" ]]; then
  echo "Full wells data: dnr_wells_full.csv"
else
  echo "Full wells data: missing — run: python3 fetch_dnr_wells.py"
fi

echo ""
echo "Next (rebuild chunks for deploy / local viewer):"
echo "  python3 build_statewide_data.py"
echo "Serve:  python3 -m http.server 8080"
