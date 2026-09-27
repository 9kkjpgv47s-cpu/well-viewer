#!/usr/bin/env python3
"""Compare v1 vs v2 classification on statewide chunks."""

from __future__ import annotations

import csv
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V2 = Path(__file__).resolve().parent
sys.path.insert(0, str(V2))
sys.path.insert(0, str(ROOT / "scripts"))

from classify_v2 import classify_well_v2, parse_lithology_json, aquifer_class  # noqa: E402
from verify_lithology_classification import derive_from_lithology  # noqa: E402

CHUNK_GLOB = "dnr_wells_chunk_*.csv.gz"


def main() -> int:
    chunks = sorted(ROOT.glob(CHUNK_GLOB))
    stats = Counter()
    for chunk in chunks:
        with gzip.open(chunk, "rt", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                layers = parse_lithology_json(row.get("lithology_json"))
                if not layers:
                    continue
                v1 = derive_from_lithology(layers)
                v2 = classify_well_v2(layers, aquifer=str(row.get("aquifer") or ""))
                aq_cls = aquifer_class(str(row.get("aquifer") or ""))

                if v1.derived_class == v2.well_type:
                    stats["agree"] += 1
                else:
                    stats[f"v1_{v1.derived_class}_v2_{v2.well_type}"] += 1

                if (
                    aq_cls == "bedrock"
                    and v1.derived_class == "unconsolidated"
                    and v2.well_type == "bedrock"
                ):
                    stats["fixed_bedrock_aq"] += 1
                if (
                    aq_cls == "bedrock"
                    and v1.derived_class != "unconsolidated"
                    and v2.well_type == "unconsolidated"
                ):
                    stats["regression_bedrock_aq"] += 1

    out = dict(stats)
    path = V2 / "docs" / "v1_v2_comparison.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
