"""
Resolve and open the statewide DNR wells export as plain CSV or gzip.

Prefer dnr_wells_full.csv when present (local edits / fetch_dnr_wells.py);
otherwise use dnr_wells_full.csv.gz from the repo — no decompress step.
"""
from __future__ import annotations

import contextlib
import gzip
import os


def resolve_dnr_full_wells_csv(out_dir: str, explicit: str | None) -> str:
    """
    Return absolute path to dnr_wells_full.csv or .csv.gz.

    If explicit is set (e.g. DNR_FULL_CSV), that path must exist.
    Otherwise: prefer .csv over .gz in out_dir.
    """
    if explicit is not None and str(explicit).strip():
        p = os.path.abspath(os.path.expanduser(str(explicit).strip()))
        if os.path.isfile(p):
            return p
        raise FileNotFoundError(f"DNR_FULL_CSV not found: {p}")

    base = os.path.join(os.path.abspath(out_dir), "dnr_wells_full.csv")
    gz = f"{base}.gz"
    if os.path.isfile(base):
        return base
    if os.path.isfile(gz):
        return gz
    raise FileNotFoundError(
        f"Need dnr_wells_full.csv or dnr_wells_full.csv.gz in {out_dir!r}. "
        "The git repo includes the .gz; run fetch_dnr_wells.py for a fresh .csv."
    )


@contextlib.contextmanager
def open_dnr_wells_csv_for_read(path: str):
    """Open text CSV stream (handles UTF-8 BOM and optional gzip)."""
    if path.lower().endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as f:
            yield f
    else:
        with open(path, newline="", encoding="utf-8-sig") as f:
            yield f
