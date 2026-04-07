#!/usr/bin/env bash
# Install Git LFS on macOS without Homebrew (puts binary in ~/bin).
# Idempotent. Run from repo root:  bash scripts/install_git_lfs_mac.sh
set -euo pipefail

LFS_VERSION="${LFS_VERSION:-v3.7.1}"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This script is for macOS only. Install Git LFS from https://git-lfs.com on other systems."
  exit 1
fi

if git lfs version &>/dev/null; then
  echo "Git LFS already available: $(git lfs version | head -1)"
  git lfs install
  exit 0
fi

ARCH="$(uname -m)"
case "$ARCH" in
  arm64) ZIP="git-lfs-darwin-arm64-${LFS_VERSION}.zip" ;;
  x86_64) ZIP="git-lfs-darwin-amd64-${LFS_VERSION}.zip" ;;
  *)
    echo "Unsupported arch: $ARCH (expected arm64 or x86_64)"
    exit 1
    ;;
esac

URL="https://github.com/git-lfs/git-lfs/releases/download/${LFS_VERSION}/${ZIP}"
TMP="${TMPDIR:-/tmp}/git-lfs-install-$$"
mkdir -p "$TMP"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

echo "Downloading Git LFS ${LFS_VERSION} (${ARCH})…"
curl -fsSL -o "$TMP/lfs.zip" "$URL"
unzip -q -o "$TMP/lfs.zip" -d "$TMP"

BIN="$(find "$TMP" -name git-lfs -type f ! -path '*/.*' | head -1)"
if [[ -z "$BIN" || ! -x "$BIN" ]]; then
  echo "Could not find git-lfs binary inside the zip."
  exit 1
fi

mkdir -p "${HOME}/bin"
install -m 0755 "$BIN" "${HOME}/bin/git-lfs"

MARK='Added for git-lfs (well-viewer)'
ZSHRC="${HOME}/.zshrc"
if ! grep -qF "${HOME}/bin" "$ZSHRC" 2>/dev/null; then
  {
    echo ""
    echo "# ${MARK}"
    echo 'export PATH="${HOME}/bin:${PATH}"'
  } >>"$ZSHRC"
  echo "Appended PATH=~/bin to $ZSHRC — run:  source ~/.zshrc"
fi

export PATH="${HOME}/bin:${PATH}"
if ! command -v git-lfs &>/dev/null; then
  echo "Add ~/bin to PATH, then run: git lfs install"
  exit 1
fi

git lfs install
echo "Done: $(git lfs version | head -1)"
