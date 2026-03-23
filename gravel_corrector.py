#!/usr/bin/env python3
"""
Used by build_other_counties.py — gravel vein / rock depth helpers from lithology rows.
Rows may be dicts with keys top, bottom, formation (strings/floats as in lithology_json).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class GravelVeinCorrector:
    GRAVEL_KEYWORDS = re.compile(
        r"(?i)(grav|gravel|s&g|sand grav|water b\.?|water bearing|water grav|"
        r"pea grav|gravelly|w/grav|producing)"
    )
    ROCK_KEYWORDS = re.compile(
        r"(?i)(limestone|dolomite|shale|sandstone|siltstone|bedrock|granite|marble|hard rock)"
    )

    @staticmethod
    def _row_fields(row: Any) -> Optional[tuple]:
        if isinstance(row, dict):
            top = row.get("top")
            bottom = row.get("bottom")
            formation = row.get("formation", "")
        else:
            top = getattr(row, "top", None)
            bottom = getattr(row, "bottom", None)
            formation = getattr(row, "formation", "")
        try:
            t, b = float(top), float(bottom)
        except (TypeError, ValueError):
            return None
        return t, b, str(formation or "")

    @classmethod
    def calculate_screen_interval(cls, construction: Dict, total_depth: float) -> tuple:
        screen_len = 0.0
        for key, val in construction.items():
            k = str(key).lower()
            if any(
                term in k
                for term in ("screen length", "screen (ft)", "screen length (ft)")
            ):
                try:
                    screen_len = float(val or 0)
                    break
                except (TypeError, ValueError):
                    pass
        if screen_len > 0:
            return total_depth - screen_len, total_depth
        return total_depth * 0.9, total_depth

    @classmethod
    def correct_gravel_vein(cls, data: Dict) -> Dict:
        construction = data.get("construction") or {}
        well_log: List[Any] = data.get("well_log") or []
        ref = data.get("reference_number")

        total_depth = float(construction.get("Depth") or construction.get("Well Depth") or 0) or 0.0
        if total_depth <= 0:
            total_depth = 100.0

        screen_top, screen_bottom = cls.calculate_screen_interval(construction, total_depth)
        rock_start: Optional[float] = None
        gravel_candidates: List[Dict] = []

        for row in well_log:
            parsed = cls._row_fields(row)
            if not parsed:
                continue
            top, bottom, formation = parsed
            if bottom <= top:
                continue
            if cls.ROCK_KEYWORDS.search(formation) and rock_start is None:
                rock_start = top
            if cls.GRAVEL_KEYWORDS.search(formation):
                overlap = max(0.0, min(bottom, screen_bottom) - max(top, screen_top))
                gravel_candidates.append(
                    {
                        "top": top,
                        "bottom": bottom,
                        "thickness_ft": bottom - top,
                        "formation": formation,
                        "overlap_with_screen_ft": overlap,
                    }
                )

        if not gravel_candidates:
            return {
                "reference_number": ref,
                "vein_size_ft": 0,
                "rock_start_ft": rock_start or 0,
            }

        selected = max(
            gravel_candidates,
            key=lambda x: (x["overlap_with_screen_ft"], x["top"]),
        )
        return {
            "reference_number": ref,
            "vein_size_ft": round(selected["thickness_ft"], 1),
            "rock_start_ft": rock_start or 0,
        }
