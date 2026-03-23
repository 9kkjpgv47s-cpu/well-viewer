#!/usr/bin/env python3
"""
Fetch pump rate and bailer rate for all Indiana DNR wells from the ArcGIS API.
Outputs a CSV mapping refno -> pump_rate (best available GPM).
"""
import csv, json, urllib.request, urllib.parse, sys

BASE_URL = "https://gisdata.in.gov/server/rest/services/Hosted/WaterWells_DNR_Water_IN_1/FeatureServer/0/query"
PAGE_SIZE = 1000
OUTPUT = "/Users/dominiceasterling/DNR_Well_Viewer_Full_Demo/dnr_pump_rates.csv"

def fetch_page(offset):
    params = {
        "where": "dblpumprate IS NOT NULL OR dblbailerrt IS NOT NULL",
        "outFields": "dblrefno,dblpumprate,dblbailerrt",
        "returnGeometry": "false",
        "resultRecordCount": PAGE_SIZE,
        "resultOffset": offset,
        "f": "json",
    }
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; Indiana-DNR-Data-Request/1.0)",
        "Referer": "https://gisdata.in.gov/",
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)

def main():
    print("Fetching pump/bailer rates from DNR ArcGIS API...")
    rows = []
    offset = 0
    while True:
        try:
            data = fetch_page(offset)
        except Exception as e:
            print(f"Error at offset {offset}: {e}", file=sys.stderr)
            break

        features = data.get("features") or []
        if not features:
            break

        for f in features:
            att = f.get("attributes") or {}
            refno = att.get("dblrefno")
            if refno is None:
                continue
            pr = att.get("dblpumprate")
            br = att.get("dblbailerrt")
            rate = pr if pr is not None and pr > 0 else (br if br is not None and br > 0 else None)
            if rate is not None:
                rows.append({"refno": int(refno), "pump_rate": rate})

        print(f"  Offset {offset}: got {len(features)} (total rates: {len(rows):,})")
        if len(features) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    with open(OUTPUT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["refno", "pump_rate"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone! {len(rows):,} wells with pump rates -> {OUTPUT}")

if __name__ == "__main__":
    main()
