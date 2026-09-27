#!/usr/bin/env python3
"""
Build formation_lexicon.json from mined vocabulary + geologic rules.

Does not modify original lithology data. Safe to re-run after re-mining.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

V2 = Path(__file__).resolve().parent
DOCS = V2 / "docs"
LEXICON_PATH = V2 / "formation_lexicon.json"

# --- Pattern rules (first match wins; order matters) ---
PATTERN_RULES: list[dict] = [
    {"id": "placeholder", "regex": r"no digitized|merged welllogs|open dnr report|placeholder|^\s*-\s*$", "category": "ignore"},
    {"id": "dry_abandon", "regex": r"dry\s*hole|no\s*water|abandon|plugged|cement\s*fill", "category": "ignore"},
    # Indiana / Midwest: "sandrock" is siliceous limestone bedrock, not sand+rock unconsolidated
    {"id": "sandrock", "regex": r"sandrock", "category": "rock"},
    {"id": "sandrock_water", "regex": r"sandrock.*\b(water|w\.|wet|producing)\b|\b(water|w\.|wet|producing).*sandrock", "category": "rock"},
    {"id": "water_bearing_stone", "regex": r"water\s*bear.*\bstone\b|\bstone\b.*water\s*bear", "category": "rock"},
    {"id": "hard_rock", "regex": r"hard\s*rock|solid\s*rock|bedrock|rip\s*rap", "category": "rock"},
    {"id": "bedrock_abbrev", "regex": r"\b(ls|lm|dl|dol)\b", "category": "rock"},
    {"id": "limestone_dolomite", "regex": r"limestone|dolomite|dolostone|lime\s*stone", "category": "rock"},
    {"id": "shale_slate", "regex": r"\bshale\b|\bslate\b|\bsh\b(?!\s*&\s*g)", "category": "rock"},
    {"id": "sandstone_siltstone", "regex": r"\bsandstone\b|\bsiltstone\b|\bquartzite\b|\bchert\b", "category": "rock"},
    {"id": "igneous_metamorphic", "regex": r"granite|marble|basalt|gneiss|schist|conglomerate|argillite", "category": "rock"},
    {"id": "coal", "regex": r"\bcoal\b", "category": "rock"},
    {"id": "gravelly_limestone", "regex": r"(lime|dolomite|shale).{0,20}grav|grav.{0,20}(lime|dolomite|shale)", "category": "mixed"},
    # Overburden — thin surface; does not define a gravel well alone
    {"id": "topsoil_fill", "regex": r"^top\s*soil$|^topsoil$|^fill$|^soil$|^surface$|^top$|^dirt$|fill\s*dirt|surface\s*fill|blanket|overburden|top\s*dirt|black\s*dirt", "category": "overburden"},
    {"id": "lime_abbrev", "regex": r"\blime\b|\bls\b|gray\s*lime|grey\s*lime|br\s*lime|hard\s*lime|sandy\s*lime", "category": "rock"},
    {"id": "ss_abbrev", "regex": r"\bss\b", "category": "rock"},
    {"id": "drift", "regex": r"\bdrift\b", "category": "unconsolidated"},
    {"id": "s_and_g", "regex": r"\bs\s+and\s+g\b", "category": "unconsolidated"},
    {"id": "water_vein", "regex": r"water\s*vein|\bvein\b|\bvain\b", "category": "unconsolidated"},
    {"id": "blank", "regex": r"^blank$", "category": "ignore"},
    # Unconsolidated aquifer materials
    {"id": "sand_gravel_explicit", "regex": r"\bs\s*&\s*g\b|\bsg\b|sand\s*/\s*g|sand\s*grav|sand\s+and\s+grav", "category": "unconsolidated"},
    {"id": "gravel", "regex": r"\bgrav\b|\bgravel\b|pea\s*grav|gravelly", "category": "unconsolidated"},
    {"id": "water_bearing_uncons", "regex": r"water\s*b\.?|water\s*bearing|water\s*grav|water\s*zone|producing", "category": "unconsolidated"},
    {"id": "drift_outwash", "regex": r"glacial\s*drift|outwash|esker|kame|till|alluv|terrace", "category": "unconsolidated"},
    {"id": "sand_sa_gr", "regex": r"\bsand\b|\bsa\b|\bgr\b(?!\s*ls)|\bfine\s+sand\b|\bcoarse\s+sand\b|\bmedium\s+sand\b", "category": "unconsolidated"},
    {"id": "clay_silt", "regex": r"\bclay\b|\bsilt\b|\bmuck\b|\bpeat\b|\bloam\b", "category": "mixed"},
    {"id": "hardpan", "regex": r"hardpan|caliche", "category": "mixed"},
    {"id": "generic_rock_word", "regex": r"\brock\b|\bstone\b", "category": "rock"},
]

# Exact overrides for high-frequency ambiguous strings (from mine + geology)
EXACT_OVERRIDES: dict[str, str] = {
    "S&G": "unconsolidated",
    "S & G": "unconsolidated",
    "SANDROCK": "rock",
    "SANDROCK WATER": "rock",
    "SANDROCK, WATER": "rock",
    "SANDROCK - WATER": "rock",
    "SANDROCK (WATER)": "rock",
    "WATER BEARING STONE": "rock",
    "GR LS": "rock",
    "GRAY LS": "rock",
    "BR LS": "rock",
    "FILL": "overburden",
    "TOPSOIL": "overburden",
    "FILL DIRT": "overburden",
    "TOP SOIL": "overburden",
    "LIME": "rock",
    "SS": "rock",
    "DRIFT": "unconsolidated",
    "S AND G": "unconsolidated",
    "HARD PAN": "mixed",
    "SOAPSTONE": "rock",
}


def classify_formation(name: str) -> tuple[str, str]:
    """Return (category, rule_id)."""
    raw = (name or "").strip()
    if not raw:
        return "ignore", "empty"
    key = raw.upper()
    if key in EXACT_OVERRIDES:
        return EXACT_OVERRIDES[key], f"exact:{key}"
    for rule in PATTERN_RULES:
        if re.search(rule["regex"], raw, re.I):
            return rule["category"], rule["id"]
    return "unknown", "none"


def main() -> int:
    inv = DOCS / "formation_vocabulary_full.csv"
    if not inv.exists():
        raise SystemExit(f"Run mine_formation_vocabulary.py first — missing {inv}")

    category_counts: dict[str, int] = {}
    exact_from_mine: dict[str, str] = {}
    unknown_top: list[tuple[int, str]] = []

    with inv.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            fm = row["formation"]
            lc = int(row["layer_count"])
            cat, _ = classify_formation(fm)
            category_counts[cat] = category_counts.get(cat, 0) + lc
            if cat == "unknown" and lc >= 50:
                unknown_top.append((lc, fm))
            # Store exact for frequent formations (>= 20 layers) for audit trail
            if lc >= 20:
                exact_from_mine[fm.upper()] = cat

    # Merge manual exact overrides
    exact_all = {**exact_from_mine, **{k.upper(): v for k, v in EXACT_OVERRIDES.items()}}

    lexicon = {
        "version": "2026-05-19",
        "description": "V2 lithology term categories — separate from v1 regex in chunks/viewer. "
        "Delete lithology_v2/ or set USE_LITHOLOGY_V2=false to revert.",
        "categories": {
            "rock": "Bedrock / consolidated matrix (counts toward rock top, not gravel well type)",
            "unconsolidated": "Sand, gravel, S&G, drift — counts toward gravel/unconsolidated well type",
            "mixed": "Clay-rich or ambiguous; thickness counted at 50% toward unconsolidated unless aquifer bedrock",
            "overburden": "Fill/topsoil — ignored for well-type unless no other signal",
            "ignore": "Placeholder, dry, abandoned",
            "unknown": "No rule matched — falls through to v2 heuristic rules in classify_v2.py",
        },
        "pattern_rules": PATTERN_RULES,
        "exact": {k: v for k, v in sorted(exact_all.items()) if v != "unknown"},
        "well_type_policy": {
            "min_unconsolidated_ft_for_gravel_well": 8,
            "trust_bedrock_aquifer_when_rock_top_present": True,
            "sandrock_always_rock": True,
            "overburden_alone_not_gravel_well": True,
        },
    }

    LEXICON_PATH.write_text(json.dumps(lexicon, indent=2), encoding="utf-8")

    report = {
        "layer_counts_by_category": category_counts,
        "exact_entries": len(exact_all),
        "unknown_formations_ge_50_layers": len(unknown_top),
        "top_unknown": [{"layers": c, "formation": fm} for c, fm in sorted(unknown_top, reverse=True)[:40]],
        "lexicon_path": str(LEXICON_PATH),
    }
    report_path = DOCS / "lexicon_build_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
