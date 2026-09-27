#!/usr/bin/env python3
"""
Build per-well v2 classification sidecar (gzip JSONL).

Does NOT modify dnr_wells_chunk_*.csv.gz or lithology_json.
Output: lithology_v2/out/well_classification_v2.jsonl.gz

Viewer/hub load this file when USE_LITHOLOGY_V2 is enabled.
"""

from __future__ import annotations

import csv
import gzip
import json
import re
import sys
from pathlib import Path

V2 = Path(__file__).resolve().parent
ROOT = V2.parent
OUT = V2 / "out"
DOCS = V2 / "docs"

sys.path.insert(0, str(V2))
from classify_v2 import classify_well_v2, parse_lithology_json, aquifer_class  # noqa: E402

CHUNK_GLOB = "dnr_wells_chunk_*.csv.gz"
PLACEHOLDER_RE = re.compile(
    r"no digitized|merged welllogs|open dnr report|placeholder", re.I
)


def litho_formation_name(layer: dict) -> str:
    for key in ("formation", "Formation", "material", "Material"):
        v = layer.get(key)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def has_real_lithology(layers: list) -> bool:
    if not layers:
        return False
    if len(layers) == 1 and PLACEHOLDER_RE.search(litho_formation_name(layers[0]) or ""):
        return False
    return True


def safe_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(str(v).strip().replace(",", ""))
    except ValueError:
        return None


def main() -> int:
    chunks = sorted(ROOT.glob(CHUNK_GLOB))
    if not chunks:
        raise SystemExit(f"No chunks in {ROOT}")

    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / "well_classification_v2.jsonl.gz"

    stats = {
        "total": 0,
        "with_real_litho": 0,
        "v2_bedrock": 0,
        "v2_unconsolidated": 0,
        "v2_unknown": 0,
        "fixed_bedrock_aq_gravel": 0,  # v1 gravel on bedrock aquifer -> v2 bedrock
        "regressions_bedrock_aq_gravel": 0,
    }
    fixes: list[dict] = []
    regressions: list[dict] = []

    # Import v1 derive for comparison
    sys.path.insert(0, str(ROOT / "scripts"))
    from verify_lithology_classification import derive_from_lithology  # noqa: E402

    with gzip.open(out_path, "wt", encoding="utf-8") as out_f:
        for chunk in chunks:
            with gzip.open(chunk, "rt", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    stats["total"] += 1
                    refno = str(row.get("refno") or "").strip()
                    if not refno:
                        continue
                    layers = parse_lithology_json(row.get("lithology_json"))
                    if not has_real_lithology(layers):
                        continue
                    stats["with_real_litho"] += 1

                    aq = str(row.get("aquifer") or "").strip()
                    v1 = derive_from_lithology(layers)
                    v2 = classify_well_v2(
                        layers,
                        aquifer=aq,
                        depth_bedrock=safe_float(row.get("depth_bedrock")),
                        depth_ft=safe_float(row.get("depth")),
                    )

                    if v2.well_type == "bedrock":
                        stats["v2_bedrock"] += 1
                    elif v2.well_type == "unconsolidated":
                        stats["v2_unconsolidated"] += 1
                    else:
                        stats["v2_unknown"] += 1

                    aq_cls = aquifer_class(aq)
                    if (
                        aq_cls == "bedrock"
                        and v1.derived_class == "unconsolidated"
                        and v2.well_type == "bedrock"
                    ):
                        stats["fixed_bedrock_aq_gravel"] += 1
                        if len(fixes) < 5000:
                            fixes.append(
                                {
                                    "refno": refno,
                                    "aquifer": aq,
                                    "v1_wb_ft": v1.water_bearing_thickness_ft,
                                    "v2_uncon_ft": v2.unconsolidated_ft,
                                    "v2_rock_top_ft": v2.rock_top_ft,
                                }
                            )
                    if (
                        aq_cls == "bedrock"
                        and v1.derived_class != "unconsolidated"
                        and v2.well_type == "unconsolidated"
                    ):
                        stats["regressions_bedrock_aq_gravel"] += 1
                        if len(regressions) < 500:
                            regressions.append({"refno": refno, "aquifer": aq})

                    rec = {
                        "refno": refno,
                        "well_type_v2": v2.well_type,
                        "label_kind_v2": v2.label_kind,
                        "unconsolidated_ft_v2": v2.unconsolidated_ft,
                        "rock_top_ft_v2": v2.rock_top_ft,
                        "ruleset_id": v2.ruleset_id,
                    }
                    out_f.write(json.dumps(rec, separators=(",", ":")) + "\n")

    summary = {
        **stats,
        "sidecar_path": str(out_path),
        "sidecar_size_mb": round(out_path.stat().st_size / 1_048_576, 2),
    }
    (DOCS / "v2_sidecar_build_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    # Sample fixes CSV
    import csv as csvmod

    fix_path = DOCS / "v2_fixed_bedrock_aquifer_wells_sample.csv"
    if fixes:
        with fix_path.open("w", newline="", encoding="utf-8") as f:
            w = csvmod.DictWriter(f, fieldnames=list(fixes[0].keys()))
            w.writeheader()
            w.writerows(fixes[:5000])

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
