#!/usr/bin/env python3
"""
Build a single CSV for the Marion County well viewer from
WellRecords + WellLogs downloads. Includes:
  - lat/lon (from existing slim CSV or UTM conversion)
  - ground_elev, depth, well_bottom_elev
  - lithology embedded as JSON
  - DNR report URL
"""
import csv, json, math, gzip, os
from collections import defaultdict

RECORDS   = "/Users/dominiceasterling/Downloads/WellRecords_96602378.csv"
LOGS      = "/Users/dominiceasterling/Downloads/WellLogs_67952275.csv"
SLIM_CSV  = "/Users/dominiceasterling/DNR_Well_Viewer_Full_Demo/dnr_wells_slim.csv"
FULL_CSV  = "/Users/dominiceasterling/DNR_Well_Viewer_Full_Demo/dnr_wells_full.csv"
OUT_DIR   = "/Users/dominiceasterling/DNR_Well_Viewer_Full_Demo"

def utm16_to_latlon(easting, northing):
    a, f = 6378137.0, 1 / 298.257223563
    e2 = 2*f - f*f
    e1 = (1 - math.sqrt(1-e2)) / (1 + math.sqrt(1-e2))
    k0 = 0.9996
    x = easting - 500000
    y = northing
    mu = y / (k0 * a * (1 - e2/4 - 3*e2**2/64))
    fp = (mu + (3*e1/2 - 27*e1**3/32)*math.sin(2*mu)
             + (21*e1**2/16 - 55*e1**4/32)*math.sin(4*mu)
             + (151*e1**3/96)*math.sin(6*mu))
    c1 = e2 * math.cos(fp)**2 / (1 - e2)
    t1 = math.tan(fp)**2
    n1 = a / math.sqrt(1 - e2*math.sin(fp)**2)
    r1 = a*(1-e2) / (1 - e2*math.sin(fp)**2)**1.5
    d = x / (n1 * k0)
    lat = fp - (n1*math.tan(fp)/r1)*(d**2/2 - (5+3*t1+10*c1-4*c1**2)*d**4/24)
    lon_rad = (d - (1+2*t1+c1)*d**3/6) / math.cos(fp)
    lon_origin = 15*6 - 180 + 3  # zone 16
    return lat * 180/math.pi, lon_origin + lon_rad * 180/math.pi

def val(row, key):
    return (row.get(key) or "").strip()

def safe_float(s):
    try: return float(s)
    except: return None

def main():
    # 1. Load lat/lon from existing slim CSV
    print("Loading lat/lon from slim CSV...")
    slim_coords = {}
    with open(SLIM_CSV, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if (row.get("county") or "").strip().upper() != "MARION": continue
            ref = (row.get("refno") or "").strip()
            if ref:
                slim_coords[ref] = (row["lat"], row["lon"])
    print(f"  {len(slim_coords)} Marion wells with lat/lon")

    # 2. Load ground_elev from full CSV (supplement)
    print("Loading supplemental elevations from full CSV...")
    full_elev = {}
    with open(FULL_CSV, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if (row.get("county") or "").strip().upper() != "MARION": continue
            ref = (row.get("refno") or "").strip()
            e = (row.get("ground_elev") or "").strip()
            if ref and e:
                full_elev[ref] = e
    print(f"  {len(full_elev)} with elevation")

    # 3. Load lithology logs
    print("Loading well logs...")
    logs = defaultdict(list)
    with open(LOGS, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            ref = val(row, "RefNum")
            if ref:
                logs[ref].append({
                    "top": val(row, "From"),
                    "bottom": val(row, "To"),
                    "formation": val(row, "Formation"),
                })
    for ref in logs:
        logs[ref].sort(key=lambda x: safe_float(x["top"]) or 0)
    print(f"  {len(logs)} wells with logs")

    # 4. Process WellRecords
    print("Processing well records...")
    out_rows = []
    skipped_no_coords = 0

    with open(RECORDS, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            ref = val(row, "RefNum")
            if not ref.isdigit():
                continue

            # Get lat/lon
            lat, lon = None, None
            if ref in slim_coords:
                lat, lon = slim_coords[ref]
            else:
                utmx = safe_float(val(row, "UTM-X"))
                utmy = safe_float(val(row, "UTM-Y"))
                if utmx and utmy:
                    lat, lon = utm16_to_latlon(utmx, utmy)
                    lat, lon = str(round(lat, 10)), str(round(lon, 10))

            if not lat or not lon:
                skipped_no_coords += 1
                continue

            # Ground elevation
            elev_str = val(row, "GrndElev")
            if not elev_str and ref in full_elev:
                elev_str = full_elev[ref]
            ground_elev = safe_float(elev_str)

            # Depth
            depth = safe_float(val(row, "Depth"))

            # Well bottom elevation from sea level
            well_bottom_elev = None
            if ground_elev is not None and depth is not None and depth > 0:
                well_bottom_elev = round(ground_elev - depth)

            # Lithology
            litho = logs.get(ref, [])
            litho_json = json.dumps(litho, separators=(",", ":")) if litho else ""

            # Well use decode
            use_code = val(row, "WellUse")
            use_map = {"H":"Domestic","I":"Industrial","C":"Commercial",
                       "A":"Agricultural","IR":"Irrigation","M":"Monitoring",
                       "PU":"Public Supply","TW":"Test Well","O":"Other"}

            # DNR report URL
            report = f"https://secure.in.gov/apps/dnr/water/dnr_waterwell?refNo={ref}&_from=SUMMARY&_action=Details"

            out_rows.append({
                "id": f"DNR-{ref}",
                "refno": ref,
                "lat": lat,
                "lon": lon,
                "depth": int(depth) if depth is not None else "",
                "county": "MARION",
                "owner": val(row, "Owner"),
                "report": report,
                "loc_type": val(row, "CivilTwp") + " TWP" if val(row, "CivilTwp") else "",
                "ground_elev": int(ground_elev) if ground_elev is not None else "",
                "well_bottom_elev": well_bottom_elev if well_bottom_elev is not None else "",
                "static_water": val(row, "Static"),
                "well_use": use_map.get(use_code, use_code),
                "casing_diam": val(row, "CasingD"),
                "casing_length": val(row, "CasingL"),
                "screen_diam": val(row, "ScreenD"),
                "screen_length": val(row, "ScreenL"),
                "pump_rate": val(row, "PumpRate"),
                "driller": val(row, "Driller"),
                "completed": val(row, "Completed") or val(row, "DateComplete"),
                "lithology_json": litho_json,
            })

    print(f"  {len(out_rows)} wells with coordinates")
    print(f"  {skipped_no_coords} skipped (no coords)")

    has_bottom = sum(1 for r in out_rows if r["well_bottom_elev"] != "")
    print(f"  {has_bottom} with pre-computed well bottom elevation")

    # 5. Write output CSV
    fields = list(out_rows[0].keys())
    out_path = os.path.join(OUT_DIR, "marion_wells.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out_rows)
    print(f"\nWrote {out_path}")

    # 6. Gzip it as a single chunk
    gz_path = os.path.join(OUT_DIR, "marion_wells_chunk_0.csv.gz")
    with open(out_path, "rb") as f_in:
        with gzip.open(gz_path, "wb") as f_out:
            f_out.write(f_in.read())
    raw = os.path.getsize(out_path)
    gz = os.path.getsize(gz_path)
    print(f"  Raw: {raw/1024/1024:.1f} MB → Gzipped: {gz/1024/1024:.1f} MB")
    print("Done!")

if __name__ == "__main__":
    main()
