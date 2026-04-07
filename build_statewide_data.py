#!/usr/bin/env python3
"""
Build statewide well data with well_bottom_elev from dnr_wells_full.csv,
plus lithology from one or more DNR WellLogs CSV/TXT files OR the official
DNR litho.txt tab export (same file the database download provides).

Log files:
  • Put surrounding-county exports in:  <this_folder>/well_logs_csv/*.csv  (or .txt tab-delimited)
  • Or set env DNR_LOGS_CSV_PATHS to colon-separated list of files (macOS/Linux use : between paths)
  • Or place litho.txt in OUT_DIR or set DNR_LITHO_TXT to its path — merges into lithology_json
    for every matching refno (this is what makes **g** labels work in the chunks).
"""
import csv, json, gzip, os, math
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.environ.get("DNR_OUT_DIR", SCRIPT_DIR)
FULL_CSV = os.environ.get("DNR_FULL_CSV", os.path.join(OUT_DIR, "dnr_wells_full.csv"))
PUMP_CSV = os.environ.get("DNR_PUMP_CSV", os.path.join(OUT_DIR, "dnr_pump_rates.csv"))
CHUNK_SIZE = int(os.environ.get("DNR_CHUNK_SIZE", "50000"))
LITHO_TXT = os.environ.get("DNR_LITHO_TXT", "").strip()
LITHO_COLS = os.environ.get("DNR_LITHO_COLS", "").strip()

def safe_float(s):
    try: return float(s)
    except: return None

def val(row, key):
    return (row.get(key) or "").strip()

def _norm_header(h):
    return (h or "").strip().lstrip("\ufeff").lower().replace(" ", "")

def discover_log_csv_paths(out_dir):
    """Resolve all WellLogs-style files to merge (Marion + surrounding counties)."""
    paths = []
    envp = os.environ.get("DNR_LOGS_CSV_PATHS") or os.environ.get("DNR_LOGS_CSV")
    if envp:
        for part in envp.replace(";", os.pathsep).split(os.pathsep):
            p = os.path.expanduser(part.strip().strip('"').strip("'"))
            if p and os.path.isfile(p):
                paths.append(p)
    well_logs_dir = os.path.join(out_dir, "well_logs_csv")
    if os.path.isdir(well_logs_dir):
        for fn in sorted(os.listdir(well_logs_dir)):
            if fn.startswith("."):
                continue
            low = fn.lower()
            if low.endswith((".csv", ".txt")):
                paths.append(os.path.join(well_logs_dir, fn))
    default_dl = os.path.expanduser("~/Downloads/WellLogs_67952275.csv")
    if not paths and os.path.isfile(default_dl):
        paths = [default_dl]
    seen, uniq = set(), []
    for p in paths:
        rp = os.path.realpath(p)
        if rp not in seen:
            seen.add(rp)
            uniq.append(p)
    return uniq

def merge_litho_txt_into_logs(logs):
    """Load DNR litho.txt into the same logs dict used by well_logs_csv (ref -> intervals)."""
    path = LITHO_TXT or os.path.join(OUT_DIR, "litho.txt")
    if not os.path.isfile(path):
        return 0
    try:
        from merge_litho_into_wells import load_lithology_from_dnr_file
    except ImportError:
        print("  WARNING: merge_litho_into_wells.py not found; cannot load litho.txt")
        return 0
    cols = LITHO_COLS if LITHO_COLS else None
    by_ref, n_wells, n_int, _delim = load_lithology_from_dnr_file(path, cols)
    if not by_ref:
        return 0
    for ref, arr in by_ref.items():
        key = str(ref)
        logs[key].extend(arr)
    print(f"  litho.txt ({os.path.basename(path)}): {n_int:,} intervals for {n_wells:,} wells")
    return n_int


def append_logs_from_file(path, logs):
    """Append lithology intervals; supports comma- or tab-separated .csv/.txt."""
    rows_added = 0
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
            first = f.readline()
            f.seek(0)
            if not first.strip():
                print(f"  WARNING: empty file {path}")
                return 0
            delim = ","
            if first.count("\t") > first.count(",") and "\t" in first:
                delim = "\t"
            reader = csv.DictReader(f, delimiter=delim)
            if not reader.fieldnames:
                print(f"  WARNING: no header in {path}")
                return 0
            fmap = {}
            for h in reader.fieldnames:
                if h is None:
                    continue
                fmap[_norm_header(h)] = h

            def col(*aliases):
                for a in aliases:
                    nk = _norm_header(a)
                    if nk in fmap:
                        return fmap[nk]
                return None

            c_ref = col("refnum", "refno", "reference", "wellid", "id")
            c_from = col("from", "top", "from_ft", "top_ft")
            c_to = col("to", "bottom", "to_ft", "bottom_ft")
            c_form = col("formation", "material", "lithology", "description", "strata")
            if not c_ref or not c_to:
                print(f"  WARNING: need RefNum + To/Bottom columns in {path}; got {reader.fieldnames!r}")
                return 0
            for row in reader:
                ref = (row.get(c_ref) or "").strip()
                if not ref:
                    continue
                logs[ref].append({
                    "top": (row.get(c_from) or "").strip() if c_from else "",
                    "bottom": (row.get(c_to) or "").strip(),
                    "formation": (row.get(c_form) or "").strip() if c_form else "",
                })
                rows_added += 1
    except OSError as e:
        print(f"  ERROR reading {path}: {e}")
        return 0
    return rows_added

def main():
    # 1. Load lithology from all discovered log files
    log_paths = discover_log_csv_paths(OUT_DIR)
    print("Loading well lithology logs...")
    logs = defaultdict(list)
    total_intervals = 0
    if not log_paths:
        print("  WARNING: No log files. Add CSV/TXT under well_logs_csv/ or set DNR_LOGS_CSV_PATHS")
    for p in log_paths:
        n = append_logs_from_file(p, logs)
        total_intervals += n
        print(f"  {os.path.basename(p)}: {n:,} intervals")
    n_txt = merge_litho_txt_into_logs(logs)
    total_intervals += n_txt
    for ref in logs:
        logs[ref].sort(key=lambda x: safe_float(x["top"]) or 0)
    print(f"  {len(logs):,} unique wells with lithology ({total_intervals:,} intervals total)")

    # 2. Load statewide pump rates
    print("Loading statewide pump rates...")
    pump_rates = {}
    with open(PUMP_CSV, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            ref = (row.get("refno") or "").strip()
            pr = safe_float((row.get("pump_rate") or "").strip())
            if ref and pr is not None and pr > 0:
                pump_rates[ref] = pr
    print(f"  {len(pump_rates):,} wells with pump rates")

    # 3. Process full statewide CSV
    print("Processing statewide wells...")
    out_rows = []
    calc_count = 0
    skip_no_coords = 0

    fields = ["id", "refno", "lat", "lon", "depth", "county", "owner", "report",
              "loc_type", "ground_elev", "well_bottom_elev", "static_water",
              "depth_bedrock", "well_use", "casing_material", "casing_diam",
              "casing_length", "screen_diam", "screen_length", "pump_type",
              "pump_rate", "lithology_json"]

    with open(FULL_CSV, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            ref = val(row, "refno")
            lat = val(row, "lat")
            lon = val(row, "lon")

            if not lat or not lon:
                skip_no_coords += 1
                continue

            lat_f = safe_float(lat)
            lon_f = safe_float(lon)
            if lat_f is None or lon_f is None or lat_f == 0 or lon_f == 0:
                skip_no_coords += 1
                continue

            ground_elev = safe_float(val(row, "ground_elev"))
            depth = safe_float(val(row, "depth"))

            well_bottom_elev = None
            if ground_elev is not None and depth is not None and depth > 0:
                well_bottom_elev = round(ground_elev - depth)
                calc_count += 1

            litho = logs.get(ref, [])
            litho_json = json.dumps(litho, separators=(",", ":")) if litho else ""

            report = val(row, "report")
            if not report and ref:
                report = f"https://secure.in.gov/apps/dnr/water/dnr_waterwell?refNo={ref}&_from=SUMMARY&_action=Details"

            depth_bedrock = safe_float(val(row, "depth_bedrock"))

            out_rows.append({
                "id": val(row, "id") or f"DNR-{ref}",
                "refno": ref,
                "lat": lat,
                "lon": lon,
                "depth": int(depth) if depth is not None else "",
                "county": val(row, "county"),
                "owner": val(row, "owner"),
                "report": report,
                "loc_type": val(row, "loc_type"),
                "ground_elev": int(ground_elev) if ground_elev is not None else "",
                "well_bottom_elev": well_bottom_elev if well_bottom_elev is not None else "",
                "static_water": val(row, "static_water"),
                "depth_bedrock": int(depth_bedrock) if depth_bedrock is not None else "",
                "well_use": val(row, "pump_type"),
                "casing_material": val(row, "casing_material"),
                "casing_diam": val(row, "casing_diam"),
                "casing_length": val(row, "casing_length"),
                "screen_diam": val(row, "screen_diam"),
                "screen_length": val(row, "screen_length"),
                "pump_type": val(row, "pump_type"),
                "pump_rate": pump_rates.get(ref, ""),
                "lithology_json": litho_json,
            })

            if len(out_rows) % 100000 == 0:
                print(f"  ...{len(out_rows):,} wells processed")

    print(f"  {len(out_rows):,} wells with coordinates")
    print(f"  {skip_no_coords:,} skipped (no coords)")
    print(f"  {calc_count:,} with pre-computed well bottom elevation")
    litho_count = sum(1 for r in out_rows if r["lithology_json"])
    print(f"  {litho_count:,} with lithology logs")

    # 3. Write chunks
    print(f"\nWriting chunks of {CHUNK_SIZE:,}...")
    total_raw = 0
    total_gz = 0
    chunk_idx = 0

    # Remove old marion-only chunks and statewide chunks
    for old in os.listdir(OUT_DIR):
        if old.startswith("statewide_wells_chunk_") and old.endswith(".csv.gz"):
            os.remove(os.path.join(OUT_DIR, old))

    for start in range(0, len(out_rows), CHUNK_SIZE):
        chunk = out_rows[start:start + CHUNK_SIZE]
        csv_path = os.path.join(OUT_DIR, f"statewide_wells_chunk_{chunk_idx}.csv")
        gz_path = csv_path + ".gz"

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(chunk)

        with open(csv_path, "rb") as f_in:
            with gzip.open(gz_path, "wb") as f_out:
                f_out.write(f_in.read())

        raw_size = os.path.getsize(csv_path)
        gz_size = os.path.getsize(gz_path)
        total_raw += raw_size
        total_gz += gz_size
        print(f"  Chunk {chunk_idx}: {len(chunk):,} wells, {raw_size/1024/1024:.1f} MB → {gz_size/1024/1024:.1f} MB gz")

        os.remove(csv_path)
        chunk_idx += 1

    print(f"\nDone! {chunk_idx} chunks written")
    print(f"  Total: {len(out_rows):,} wells")
    print(f"  Raw: {total_raw/1024/1024:.1f} MB → Gzipped: {total_gz/1024/1024:.1f} MB")

if __name__ == "__main__":
    main()
