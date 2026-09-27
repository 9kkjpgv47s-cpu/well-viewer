#!/usr/bin/env python3
"""
Scan statewide well chunks and build a complete formation-term inventory.

Does NOT modify chunks, lithology_json, or any original lithology sources.
Outputs live under lithology_v2/docs/ only.
"""

from __future__ import annotations

import csv
import gzip
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V2 = Path(__file__).resolve().parent
DOCS = V2 / "docs"
CHUNK_GLOB = "dnr_wells_chunk_*.csv.gz"

# Import v1 rules for comparison (read-only)
sys.path.insert(0, str(ROOT / "scripts"))
from verify_lithology_classification import (  # noqa: E402
    aquifer_class,
    derive_from_lithology,
    is_water_bearing_formation,
    looks_like_sand_gravel_material,
    parse_lithology,
    litho_formation_name,
    ROCK_RE,
)

PLACEHOLDER_RE = re.compile(
    r"no digitized|merged welllogs|open dnr report|placeholder", re.I
)

# Tokenize formation text into words/abbreviations for frequency analysis
WORD_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?", re.I)
ABBREV_RE = re.compile(r"\b([a-z]{1,4})\b", re.I)


def normalize_formation(raw: str) -> str:
    s = " ".join((raw or "").split()).strip()
    return s


def formation_tokens(text: str) -> list[str]:
    return [m.group(0).lower() for m in WORD_RE.finditer(text or "")]


def v1_flags(name: str) -> dict[str, bool]:
    l = (name or "").lower()
    return {
        "water_bearing": is_water_bearing_formation(name),
        "sand_gravel": looks_like_sand_gravel_material(name),
        "rock_signal": bool(ROCK_RE.search(l)),
    }


def main() -> int:
    chunks = sorted(ROOT.glob(CHUNK_GLOB))
    if not chunks:
        raise SystemExit(f"No chunks: {ROOT / CHUNK_GLOB}")

    formation_counts: Counter[str] = Counter()
    formation_well_refs: dict[str, set[str]] = defaultdict(set)
    formation_layer_count: Counter[str] = Counter()
    word_counts: Counter[str] = Counter()
    word_in_formations: dict[str, set[str]] = defaultdict(set)

    # Per-formation aggregate v1 signals + aquifer context
    formation_meta: dict[str, dict] = {}

    bedrock_aq_misclassified_gravel: list[dict] = []
    rock_aq_refs: set[str] = set()

    total_layers = 0
    total_wells = 0

    for chunk in chunks:
        with gzip.open(chunk, "rt", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_wells += 1
                refno = str(row.get("refno") or "").strip()
                aq = str(row.get("aquifer") or "").strip()
                aq_cls = aquifer_class(aq)
                if aq_cls == "bedrock":
                    rock_aq_refs.add(refno)

                layers = parse_lithology(row.get("lithology_json"))
                if not layers:
                    continue
                if len(layers) == 1 and PLACEHOLDER_RE.search(
                    litho_formation_name(layers[0]) or ""
                ):
                    continue

                derived = derive_from_lithology(layers)
                if (
                    aq_cls == "bedrock"
                    and derived.derived_class == "unconsolidated"
                    and refno
                ):
                    bedrock_aq_misclassified_gravel.append(
                        {
                            "refno": refno,
                            "aquifer": aq,
                            "wb_ft": derived.water_bearing_thickness_ft,
                            "rock_top_ft": derived.rock_top_ft,
                        }
                    )

                prev_bot = float("nan")
                for layer in layers:
                    fm = normalize_formation(litho_formation_name(layer))
                    if not fm or PLACEHOLDER_RE.search(fm):
                        continue
                    total_layers += 1
                    formation_counts[fm] += 1
                    formation_layer_count[fm] += 1
                    if refno:
                        formation_well_refs[fm].add(refno)

                    for tok in formation_tokens(fm):
                        word_counts[tok] += 1
                        word_in_formations[tok].add(fm)

                    flags = v1_flags(fm)
                    meta = formation_meta.setdefault(
                        fm,
                        {
                            "formation": fm,
                            "layer_count": 0,
                            "well_count": 0,
                            "v1_water_bearing_layers": 0,
                            "v1_sand_gravel_layers": 0,
                            "v1_rock_signal_layers": 0,
                            "bedrock_aquifer_well_count": 0,
                            "unconsolidated_aquifer_well_count": 0,
                        },
                    )
                    meta["layer_count"] += 1
                    if flags["water_bearing"]:
                        meta["v1_water_bearing_layers"] += 1
                    if flags["sand_gravel"]:
                        meta["v1_sand_gravel_layers"] += 1
                    if flags["rock_signal"]:
                        meta["v1_rock_signal_layers"] += 1

    for fm, refs in formation_well_refs.items():
        meta = formation_meta[fm]
        meta["well_count"] = len(refs)
        bedrock_ct = sum(1 for r in refs if r in rock_aq_refs)
        meta["bedrock_aquifer_well_count"] = bedrock_ct
        meta["unconsolidated_aquifer_well_count"] = len(refs) - bedrock_ct

    DOCS.mkdir(parents=True, exist_ok=True)

    # Full formation inventory CSV
    inv_path = DOCS / "formation_vocabulary_full.csv"
    fields = [
        "formation",
        "layer_count",
        "well_count",
        "v1_water_bearing_layers",
        "v1_sand_gravel_layers",
        "v1_rock_signal_layers",
        "bedrock_aquifer_well_count",
        "unconsolidated_aquifer_well_count",
        "pct_layers_v1_water_bearing",
        "pct_layers_v1_rock",
    ]
    rows = []
    for fm, c in formation_counts.most_common():
        m = formation_meta[fm]
        lc = m["layer_count"] or 1
        rows.append(
            {
                "formation": fm,
                "layer_count": c,
                "well_count": m["well_count"],
                "v1_water_bearing_layers": m["v1_water_bearing_layers"],
                "v1_sand_gravel_layers": m["v1_sand_gravel_layers"],
                "v1_rock_signal_layers": m["v1_rock_signal_layers"],
                "bedrock_aquifer_well_count": m["bedrock_aquifer_well_count"],
                "unconsolidated_aquifer_well_count": m["unconsolidated_aquifer_well_count"],
                "pct_layers_v1_water_bearing": round(
                    100 * m["v1_water_bearing_layers"] / lc, 2
                ),
                "pct_layers_v1_rock": round(
                    100 * m["v1_rock_signal_layers"] / lc, 2
                ),
            }
        )
    with inv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    # Word frequency CSV
    word_path = DOCS / "formation_word_frequency.csv"
    with word_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["word", "token_count", "distinct_formations"],
        )
        w.writeheader()
        for word, ct in word_counts.most_common():
            w.writerow(
                {
                    "word": word,
                    "token_count": ct,
                    "distinct_formations": len(word_in_formations[word]),
                }
            )

    # Bedrock aquifer wells that v1 lithology classifies as gravel
    mismatch_path = DOCS / "bedrock_aquifer_v1_gravel_wells.csv"
    with mismatch_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["refno", "aquifer", "wb_ft", "rock_top_ft"],
        )
        w.writeheader()
        w.writerows(bedrock_aq_misclassified_gravel)

    summary = {
        "total_wells_scanned": total_wells,
        "total_lithology_layers": total_layers,
        "distinct_formations": len(formation_counts),
        "distinct_words": len(word_counts),
        "bedrock_aquifer_v1_gravel_well_count": len(bedrock_aq_misclassified_gravel),
        "output_files": {
            "formation_vocabulary_full": str(inv_path),
            "formation_word_frequency": str(word_path),
            "bedrock_aquifer_v1_gravel_wells": str(mismatch_path),
        },
    }
    summary_path = DOCS / "vocabulary_mine_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
