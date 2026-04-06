"""
Optional local secrets / overrides for DNR build scripts.

Loads `.env.local` from this repo root (same folder as this file) if present.
Existing `os.environ` entries are never overwritten (shell / CI wins).

`.env*.local` is gitignored — commit this module, not your secrets file.
"""
from __future__ import annotations

import os


def ensure_dnr_env_local_loaded() -> None:
    root = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(root, ".env.local")
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "=" not in s:
            continue
        key, _, rest = s.partition("=")
        key = key.strip()
        if not key:
            continue
        val = rest.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        if key not in os.environ:
            os.environ[key] = val
