#!/usr/bin/env python3
"""
Fetch the full Indiana DNR water well dataset from the official ArcGIS REST API
and save as dnr_wells_full.csv. No scraping — uses the public API.

Run:  python3 fetch_dnr_wells.py
Requires: Python 3 (no extra packages). Needs internet.
"""
import argparse
import csv
import json
import urllib.request
import urllib.parse
import sys

BASE_URL = "https://gisdata.in.gov/server/rest/services/Hosted/WaterWells_DNR_Water_IN_1/FeatureServer/0/query"
PAGE_SIZE = 1000  # API max is 1000 per request
OUTPUT_FILE = "dnr_wells_full.csv"

# All attribute fields we want (geometry comes separately as x,y in WGS84)
OUT_FIELDS = (
    "dblrefno,dbldepth,strowner,strcounty,loc_type,report,"
    "utmx_nad83,utmy_nad83,dblutmx,dblutmy,dtmcompdate,dblgrndelev,"
    "strtwn1,strrng1,dblsec1,strtopo,dblstatic,dblbedrocke,dblbedrockd,"
    "strcasingm,dblcasingd,dblcasingl,dblscreend,dblscreenl,strpumptypedesc"
)


def fetch_page(offset: int) -> dict:
    params = {
        "where": "1=1",
        "outFields": OUT_FIELDS,
        "returnGeometry": "true",
        "outSR": "4326",  # WGS84 lat/lon
        "resultRecordCount": PAGE_SIZE,
        "resultOffset": offset,
        "f": "json",
    }
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; Indiana-DNR-Data-Request/1.0)",
            "Referer": "https://gisdata.in.gov/",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def feature_to_row(f: dict) -> dict:
    att = f.get("attributes") or {}
    geom = f.get("geometry") or {}
    # Geometry is x=lon, y=lat when outSR=4326
    lon = geom.get("x")
    lat = geom.get("y")
    if lat is None or lon is None:
        return None
    refno = att.get("dblrefno")
    return {
        "refno": int(refno) if refno is not None else "",
        "lat": lat,
        "lon": lon,
        "depth": att.get("dbldepth") or "",
        "county": att.get("strcounty") or "",
        "owner": (att.get("strowner") or "")[:100],  # avoid huge fields
        "loc_type": att.get("loc_type") or "",
        "report": att.get("report") or "",
        "utm_x": att.get("utmx_nad83") or att.get("dblutmx") or "",
        "utm_y": att.get("utmy_nad83") or att.get("dblutmy") or "",
        "date_complete": att.get("dtmcompdate") or "",
        "ground_elev": att.get("dblgrndelev") or "",
        "township": att.get("strtwn1") or "",
        "range": att.get("strrng1") or "",
        "section": att.get("dblsec1") or "",
        "topo": att.get("strtopo") or "",
        "static_water": att.get("dblstatic") or "",
        "bedrock_elev": att.get("dblbedrocke") or "",
        "depth_bedrock": att.get("dblbedrockd") or "",
        "casing_material": att.get("strcasingm") or "",
        "casing_diam": att.get("dblcasingd") or "",
        "casing_length": att.get("dblcasingl") or "",
        "screen_diam": att.get("dblscreend") or "",
        "screen_length": att.get("dblscreenl") or "",
        "pump_type": att.get("strpumptypedesc") or "",
    }


def main():
    p = argparse.ArgumentParser(description="Fetch full DNR well dataset from ArcGIS API into dnr_wells_full.csv")
    p.add_argument("--limit", type=int, default=0, help="Max wells to fetch (0 = all). Use e.g. 2000 to test.")
    args = p.parse_args()

    print("Fetching Indiana DNR water wells from the official ArcGIS API...")
    print("(This is not scraping — it's the public REST API.)\n")

    rows = []
    offset = 0
    while True:
        try:
            data = fetch_page(offset)
        except Exception as e:
            print(f"Error fetching offset {offset}: {e}", file=sys.stderr)
            sys.exit(1)

        features = data.get("features") or []
        if not features:
            break

        for f in features:
            if args.limit and len(rows) >= args.limit:
                break
            row = feature_to_row(f)
            if row:
                rows.append(row)

        n = len(features)
        print(f"  Offset {offset}: got {n} wells (total so far: {len(rows)})")
        if n < PAGE_SIZE or (args.limit and len(rows) >= args.limit):
            break
        offset += PAGE_SIZE

    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        print("No wells returned. Check API or try again.", file=sys.stderr)
        sys.exit(1)

    fieldnames = list(rows[0].keys())
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"\nWrote {len(rows):,} wells to {OUTPUT_FILE}")
    print("Next: run your app or deploy; it will load this file on open.")


if __name__ == "__main__":
    main()
