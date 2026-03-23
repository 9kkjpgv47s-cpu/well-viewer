#!/usr/bin/env python3
"""
Merge WellRecords and WellLogs CSVs into a single unified text document.
Each well gets a clean block with record info + lithology log.
"""

import csv
import sys
from collections import defaultdict

RECORDS_CSV = "/Users/dominiceasterling/Downloads/WellRecords_96602378.csv"
LOGS_CSV    = "/Users/dominiceasterling/Downloads/WellLogs_67952275.csv"
OUTPUT_FILE = "/Users/dominiceasterling/DNR_Well_Viewer_Full_Demo/marion_wells_unified.txt"

WELL_USE_CODES = {
    "H": "Domestic/Household", "I": "Industrial", "C": "Commercial",
    "A": "Agricultural", "IR": "Irrigation", "M": "Monitoring",
    "PU": "Public Supply", "TW": "Test Well", "O": "Other",
}

METHOD_CODES = {
    "R": "Rotary", "C": "Cable", "D": "Driven", "B": "Bored",
    "J": "Jetted", "A": "Auger", "H": "Hand Dug",
}

def val(row, key):
    """Return stripped value or empty string."""
    return (row.get(key) or "").strip()

def fmt_date(raw):
    """Clean up '5/8/1992 12:00:00 AM' → '05/08/1992'."""
    if not raw:
        return ""
    raw = raw.strip()
    date_part = raw.split(" ")[0]
    parts = date_part.split("/")
    if len(parts) == 3:
        return f"{int(parts[0]):02d}/{int(parts[1]):02d}/{parts[2]}"
    return raw

def load_logs(path):
    """Load well logs grouped by RefNum."""
    logs = defaultdict(list)
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ref = val(row, "RefNum")
            if ref:
                logs[ref].append({
                    "from": val(row, "From"),
                    "to":   val(row, "To"),
                    "form": val(row, "Formation"),
                })
    for ref in logs:
        logs[ref].sort(key=lambda x: float(x["from"]) if x["from"] else 0)
    return logs

def format_well(rec, log_layers):
    """Format a single well block."""
    ref      = val(rec, "RefNum")
    county   = val(rec, "County1") or val(rec, "County")
    twp_name = val(rec, "CivilTwp")
    completed = val(rec, "Completed") or fmt_date(val(rec, "DateComplete"))

    header_parts = [f"WELL #{ref}"]
    if county:
        header_parts.append(f"{county} COUNTY")
    if twp_name:
        header_parts.append(f"{twp_name} TWP")
    if completed:
        header_parts.append(f"Completed: {completed}")

    sep = "=" * 80
    lines = [sep, "  |  ".join(header_parts), sep, ""]

    # --- LOCATION ---
    twp = val(rec, "Twp1") or val(rec, "Twn")
    rng = val(rec, "Rng1") or val(rec, "Rng")
    sec = val(rec, "Sec1") or val(rec, "Sec")
    topo = val(rec, "Topo")
    q1, q2, q3 = val(rec, "Quar1"), val(rec, "Quar2"), val(rec, "Quar3")
    quarter = " ".join(filter(None, [q1, q2, q3]))
    directions = val(rec, "DriveDir")
    utm_x, utm_y = val(rec, "UTM-X"), val(rec, "UTM-Y")
    elev = val(rec, "GrndElev")

    loc_lines = []
    if twp or rng or sec:
        loc_lines.append(f"  Township: {twp}   Range: {rng}   Section: {sec}")
    if quarter:
        loc_lines.append(f"  Quarter: {quarter}")
    if topo:
        loc_lines.append(f"  Topo Quad: {topo}")
    if utm_x and utm_y:
        loc_lines.append(f"  UTM: {utm_x} E, {utm_y} N")
    if elev:
        loc_lines.append(f"  Ground Elevation: {elev} ft")
    if directions:
        loc_lines.append(f"  Directions: {directions}")

    if loc_lines:
        lines.append("LOCATION")
        lines.extend(loc_lines)
        lines.append("")

    # --- WELL DETAILS ---
    depth    = val(rec, "Depth")
    static   = val(rec, "Static")
    use_code = val(rec, "WellUse")
    use_desc = WELL_USE_CODES.get(use_code, use_code)
    meth_code = val(rec, "Method")
    meth_desc = METHOD_CODES.get(meth_code, meth_code)
    well_type = val(rec, "WellType")
    quality  = val(rec, "Quality")
    bedrock_d = val(rec, "BedRockD")
    bedrock_e = val(rec, "BedRockE")

    det_lines = []
    if depth:
        det_lines.append(f"  Total Depth: {depth} ft")
    if static:
        det_lines.append(f"  Static Water Level: {static} ft")
    if use_desc:
        det_lines.append(f"  Well Use: {use_desc}")
    if well_type:
        det_lines.append(f"  Well Type: {well_type}")
    if meth_desc:
        det_lines.append(f"  Drill Method: {meth_desc}")
    if quality:
        det_lines.append(f"  Water Quality: {quality}")
    if bedrock_d:
        det_lines.append(f"  Depth to Bedrock: {bedrock_d} ft")
    if bedrock_e:
        det_lines.append(f"  Bedrock Elevation: {bedrock_e} ft")

    if det_lines:
        lines.append("WELL DETAILS")
        lines.extend(det_lines)
        lines.append("")

    # --- CASING & SCREEN ---
    cas_l = val(rec, "CasingL")
    cas_d = val(rec, "CasingD")
    cas_m = val(rec, "CasingM")
    scr_l = val(rec, "ScreenL")
    scr_d = val(rec, "ScreenD")
    scr_m = val(rec, "ScreenM")
    slot  = val(rec, "Slot")

    cs_lines = []
    if cas_l or cas_d or cas_m:
        parts = []
        if cas_l: parts.append(f"{cas_l} ft")
        if cas_d: parts.append(f'{cas_d}" dia')
        if cas_m: parts.append(cas_m)
        cs_lines.append(f"  Casing: {', '.join(parts)}")
    if scr_l or scr_d or scr_m:
        parts = []
        if scr_l: parts.append(f"{scr_l} ft")
        if scr_d: parts.append(f'{scr_d}" dia')
        if scr_m: parts.append(scr_m)
        if slot:  parts.append(f"Slot {slot}")
        cs_lines.append(f"  Screen: {', '.join(parts)}")

    if cs_lines:
        lines.append("CASING & SCREEN")
        lines.extend(cs_lines)
        lines.append("")

    # --- PUMP & YIELD ---
    pump_type = val(rec, "PumpType")
    pump_set  = val(rec, "PumpSet")
    rate      = val(rec, "PumpRate")
    hours     = val(rec, "PumpHour")
    drawdown  = val(rec, "PumpDW")
    test_type = val(rec, "TypeTest")

    py_lines = []
    if pump_type:
        py_lines.append(f"  Pump Type: {pump_type}")
    if pump_set:
        py_lines.append(f"  Pump Set At: {pump_set} ft")
    if rate:
        s = f"  Pump Rate: {rate} gpm"
        if hours:
            s += f" for {hours} hr"
        if drawdown:
            s += f", drawdown {drawdown} ft"
        py_lines.append(s)

    if py_lines:
        lines.append("PUMP & YIELD")
        lines.extend(py_lines)
        lines.append("")

    # --- GROUT & SEAL ---
    grout_m = val(rec, "GroutM")
    grout_f = val(rec, "GroutF")
    grout_t = val(rec, "GroutT")
    grout_method = val(rec, "MethodG")
    grout_bags   = val(rec, "GroutBags")

    gr_lines = []
    if grout_m:
        s = f"  Material: {grout_m}"
        if grout_f or grout_t:
            s += f"  (From {grout_f} ft to {grout_t} ft)"
        gr_lines.append(s)
    if grout_method:
        gr_lines.append(f"  Method: {grout_method}")
    if grout_bags:
        gr_lines.append(f"  Bags: {grout_bags}")

    if gr_lines:
        lines.append("GROUT & SEAL")
        lines.extend(gr_lines)
        lines.append("")

    # --- OWNER ---
    owner      = val(rec, "Owner")
    owner_addr = val(rec, "OwnerAddr")
    owner_zip  = val(rec, "OwnerZip")
    owner_ph   = val(rec, "OwnerPhone")

    if owner:
        lines.append("OWNER")
        lines.append(f"  {owner}")
        if owner_addr:
            addr = owner_addr
            if owner_zip:
                addr += f" {owner_zip}"
            lines.append(f"  {addr}")
        if owner_ph:
            lines.append(f"  Phone: {owner_ph}")
        lines.append("")

    # --- DRILLER ---
    driller      = val(rec, "Driller")
    driller_addr = val(rec, "DrillerAddr")
    driller_zip  = val(rec, "DrillerZip")
    driller_ph   = val(rec, "DrillerPhone")
    operator     = val(rec, "Operator")
    license_no   = val(rec, "License")

    if driller:
        lines.append("DRILLER")
        lines.append(f"  {driller}")
        if driller_addr:
            addr = driller_addr
            if driller_zip:
                addr += f" {driller_zip}"
            lines.append(f"  {addr}")
        if driller_ph:
            lines.append(f"  Phone: {driller_ph}")
        if operator:
            s = f"  Operator: {operator}"
            if license_no:
                s += f"  (License #{license_no})"
            lines.append(s)
        lines.append("")

    # --- COMMENT ---
    comment = val(rec, "Comment")
    if comment:
        lines.append("NOTES")
        lines.append(f"  {comment}")
        lines.append("")

    # --- LITHOLOGY LOG ---
    if log_layers:
        lines.append("LITHOLOGY LOG")
        lines.append(f"  {'Depth (ft)':<16}Formation")
        lines.append(f"  {'─' * 14}  {'─' * 30}")
        for layer in log_layers:
            depth_range = f"{layer['from']} - {layer['to']}"
            lines.append(f"  {depth_range:<16}{layer['form']}")
        lines.append("")
    else:
        lines.append("LITHOLOGY LOG")
        lines.append("  (No log data on file)")
        lines.append("")

    return "\n".join(lines)


def main():
    print("Loading well logs...")
    logs = load_logs(LOGS_CSV)
    print(f"  {len(logs)} wells with lithology data")

    print("Loading well records...")
    records = []
    skipped = 0
    with open(RECORDS_CSV, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ref = val(row, "RefNum")
            if ref.isdigit():
                records.append(row)
            else:
                skipped += 1
    print(f"  {len(records)} well records ({skipped} malformed rows skipped)")

    records.sort(key=lambda r: int(val(r, "RefNum")) if val(r, "RefNum").isdigit() else 0)

    print("Building unified document...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        out.write("MARION COUNTY DNR WELL RECORDS — UNIFIED DOCUMENT\n")
        out.write(f"Generated from WellRecords + WellLogs data\n")
        out.write(f"Total Wells: {len(records)}   |   Wells with Logs: {len(logs)}\n")
        out.write("=" * 80 + "\n\n")

        for i, rec in enumerate(records):
            ref = val(rec, "RefNum")
            well_logs = logs.get(ref, [])
            out.write(format_well(rec, well_logs))
            out.write("\n")

            if (i + 1) % 5000 == 0:
                print(f"  ...{i + 1} wells written")

    print(f"\nDone! Output: {OUTPUT_FILE}")
    print(f"  {len(records)} wells written")

if __name__ == "__main__":
    main()
