#!/usr/bin/env python3
"""
V2 lithology / well-type classifier using formation_lexicon.json.

Uses the same well-level decision flow as v1 (verify_lithology_classification.py)
but classifies each formation layer through the v2 lexicon first.

Independent of original lithology_json — reads layers in memory only.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

V2_DIR = Path(__file__).resolve().parent
LEXICON_PATH = V2_DIR / "formation_lexicon.json"

DRY_RE = re.compile(r"dry\s*hole|no\s*water|abandon|plugged|cement\s*fill", re.I)
ROCK_AQ_RE = re.compile(
    r"bedrock|limestone|dolomite|dolostone|shale|sandstone|siltstone|granite|marble",
    re.I,
)
UNCON_AQ_RE = re.compile(r"unconsolidated|sand|gravel|drift|outwash", re.I)
ROCK_RE = re.compile(
    r"lime|dolomite|shale|slate|sandstone|siltstone|bedrock|granite|marble|rock",
    re.I,
)


def litho_parse_depth(v: Any) -> float:
    if v is None:
        return float("nan")
    s = str(v).strip()
    if not s:
        return float("nan")
    s = re.sub(r"[^0-9.\-]", "", s)
    if not s:
        return float("nan")
    try:
        return float(s)
    except ValueError:
        return float("nan")


def litho_formation_name(layer: dict[str, Any]) -> str:
    for key in (
        "formation",
        "Formation",
        "material",
        "Material",
        "lithology",
        "Lithology",
        "description",
        "strata",
    ):
        v = layer.get(key)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def litho_top_bottom(layer: dict[str, Any], prev_bot: float) -> tuple[float, float]:
    top = litho_parse_depth(
        layer.get("top")
        or layer.get("Top")
        or layer.get("from")
        or layer.get("From")
        or layer.get("depth_top")
        or layer.get("StartDepth")
    )
    bot = litho_parse_depth(
        layer.get("bottom")
        or layer.get("Bottom")
        or layer.get("to")
        or layer.get("To")
        or layer.get("depth_bottom")
        or layer.get("EndDepth")
    )
    if bot != bot:
        return (top, bot)
    if top != top:
        top = 0.0 if prev_bot != prev_bot else prev_bot
    return (top, bot)


@lru_cache(maxsize=1)
def load_lexicon() -> dict[str, Any]:
    data = json.loads(LEXICON_PATH.read_text(encoding="utf-8"))
    patterns = [
        (rule["id"], re.compile(rule["regex"], re.I), rule["category"])
        for rule in data.get("pattern_rules", [])
    ]
    exact = {k.upper(): v for k, v in (data.get("exact") or {}).items()}
    policy = data.get("well_type_policy") or {}
    return {
        "patterns": patterns,
        "exact": exact,
        "policy": policy,
        "version": data.get("version", ""),
    }


def formation_category_v2(name: str) -> tuple[str, str]:
    lex = load_lexicon()
    raw = (name or "").strip()
    if not raw:
        return "ignore", "empty"
    if DRY_RE.search(raw):
        return "ignore", "dry"
    key = raw.upper()
    if key in lex["exact"]:
        return lex["exact"][key], f"exact:{key}"
    for rule_id, rx, cat in lex["patterns"]:
        if rx.search(raw):
            return cat, rule_id
    return "unknown", "none"


def layer_counts_toward_unconsolidated(category: str, fm: str) -> bool:
    """Whether this layer adds to water-bearing / gravel thickness (v2)."""
    if category == "unconsolidated":
        return True
    if category in ("rock", "overburden", "ignore"):
        return False
    if category == "mixed":
        # Clay mixes with S&G still count; pure clay pan does not
        l = fm.lower()
        return bool(re.search(r"grav|gravel|\bsg\b|s\s*&\s*g|sand\s*grav|s\s+and\s+g", l, re.I))
    # unknown — mirror v1 fallback without sandrock false positives
    l = fm.lower()
    if re.search(r"sandrock", l, re.I):
        return False
    if ROCK_RE.search(l) and not re.search(
        r"sand|grav|gravel|drift|sa\b|gr\b|sg\b|outwash|till", l, re.I
    ):
        return False
    return bool(
        re.search(
            r"grav|gravel|\bsg\b|s\s*&\s*g|sand\s*grav|water\s*b\.?|water\s*bearing|"
            r"outwash|drift|till|\bsand\b|\bsa\b|\bgr\b",
            l,
            re.I,
        )
    )


def layer_is_rock_top_signal(category: str, fm: str) -> bool:
    if category == "rock":
        return True
    if category in ("unconsolidated", "overburden", "ignore"):
        return False
    l = fm.lower()
    return bool(
        ROCK_RE.search(l)
        and "sand and" not in l
        and "gravel" not in l
        and not re.search(r"sandrock", l, re.I)
    )


def aquifer_class(aq: str) -> str:
    s = (aq or "").strip()
    if not s:
        return "unknown"
    if ROCK_AQ_RE.search(s):
        return "bedrock"
    if UNCON_AQ_RE.search(s):
        return "unconsolidated"
    return "unknown"


@dataclass
class WellClassificationV2:
    well_type: str  # bedrock | unconsolidated | unknown
    label_kind: str  # g | r | none
    unconsolidated_ft: float | None
    rock_top_ft: float | None
    ruleset_id: str
    dominant_categories: dict[str, float]


def classify_well_v2(
    layers: list[dict[str, Any]],
    *,
    aquifer: str = "",
    depth_bedrock: float | None = None,
    depth_ft: float | None = None,
) -> WellClassificationV2:
    policy = load_lexicon()["policy"]
    min_uncon_override = float(policy.get("min_unconsolidated_ft_for_gravel_well", 8))
    trust_bedrock_aq = bool(policy.get("trust_bedrock_aquifer_when_rock_top_present", True))

    aq_cls = aquifer_class(aquifer)
    prev_bot = float("nan")
    rock_top: float | None = None
    wb_sum = 0.0
    cat_thickness: dict[str, float] = {}
    only_overburden_uncon = True
    had_sandrock_misread = False

    for layer in layers:
        fm = litho_formation_name(layer)
        top, bot = litho_top_bottom(layer, prev_bot)
        if bot == bot:
            prev_bot = bot
        if bot != bot or top != top or bot <= top:
            continue
        thick = bot - top
        cat, rule_id = formation_category_v2(fm)
        cat_thickness[cat] = cat_thickness.get(cat, 0.0) + thick

        l = fm.lower()
        if (
            rock_top is None
            and layer_is_rock_top_signal(cat, fm)
            and top == top
            and top >= 0
        ):
            rock_top = top

        if layer_counts_toward_unconsolidated(cat, fm):
            wb_sum += thick
            if cat != "overburden":
                only_overburden_uncon = False
            if re.search(r"sandrock", l, re.I) and re.search(
                r"water|w\.|wet|producing", l, re.I
            ):
                had_sandrock_misread = True

    wb = int(round(wb_sum)) if wb_sum > 0 else None

    if depth_bedrock is not None and depth_bedrock > 0:
        if rock_top is None:
            rock_top = depth_bedrock
        else:
            rock_top = min(rock_top, depth_bedrock)

    # --- Well type (aligned with v1 derive_from_lithology) ---
    well_type = "unknown"
    label_kind = "none"

    if wb and wb > 0:
        well_type = "unconsolidated"
        label_kind = "g"
    elif rock_top is not None and rock_top > 0:
        well_type = "bedrock"
        label_kind = "r"

    # Targeted fixes for known false gravel on rock wells
    if well_type == "unconsolidated" and aq_cls == "bedrock":
        # Sandrock + water is bedrock, not gravel
        if had_sandrock_misread and (wb or 0) < 80:
            well_type = "bedrock"
            label_kind = "r" if rock_top else "none"
            wb = None
        # Thin surface fill/S&G over known rock — trust bedrock aquifer + rock top
        elif (
            trust_bedrock_aq
            and rock_top is not None
            and (wb or 0) < min_uncon_override
        ):
            well_type = "bedrock"
            label_kind = "r"
            wb = None
        elif only_overburden_uncon and rock_top is not None:
            well_type = "bedrock"
            label_kind = "r"
            wb = None

    return WellClassificationV2(
        well_type=well_type,
        label_kind=label_kind,
        unconsolidated_ft=float(wb) if wb else None,
        rock_top_ft=int(round(rock_top)) if rock_top is not None else None,
        ruleset_id=str(load_lexicon().get("version", "v2")),
        dominant_categories={k: round(v, 1) for k, v in sorted(cat_thickness.items())},
    )


def parse_lithology_json(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    s = str(raw).strip()
    if not s:
        return []
    try:
        j = json.loads(s)
    except Exception:
        return []
    if isinstance(j, list):
        return [x for x in j if isinstance(x, dict)]
    return []
