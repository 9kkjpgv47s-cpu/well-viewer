#!/usr/bin/env python3
"""
Merge Indiana DNR litho.txt into:
  (1) Optional CSV column lithology_json on dnr_wells_full.csv
  (2) REQUIRED for app: litho_parts/litho_NNN.json — one file per refno block (refno // 10000)
      so the viewer can fetch Well Log without huge CSV rows.

The app loads:  /litho_parts/litho_17.json  for refno 174349 (174349 // 10000 = 17)
Each JSON: { "174349": [{"top":"0","bottom":"45","formation":"SOFT CLAY"}, ...], ... }

Usage:
  python3 merge_litho_into_wells.py litho.txt dnr_wells_full.csv
  # Creates litho_parts/litho_*.json — deploy that folder with the site.
"""
import argparse
import csv
import json
import os
import re
import sys

DEFAULT_PART = 1000  # refno // PART → filename litho_N.json. Smaller = safer for Vercel file size limits.


def normalize_header(h):
    return re.sub(r"[^a-z0-9]", "", (h or "").lower())


def looks_like_refno(s):
    s = str(s).strip()
    if not s:
        return False
    try:
        v = float(s.replace(",", ""))
        return 1 <= v <= 999999999
    except ValueError:
        return False


def read_litho_rows(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    sample = "\n".join(lines[:50])
    delim = "\t" if sample.count("\t") >= sample.count(",") else ","
    return list(csv.reader(lines, delimiter=delim)), delim


def detect_columns(rows):
    if not rows:
        return 0, 1, 2, 3
    first = " ".join(normalize_header(c) for c in rows[0])

    def find(names, cells):
        for name in names:
            for i, c in enumerate(cells):
                h = normalize_header(c)
                if name in h or h in name:
                    return i
        return None

    has_header = ("top" in first and "bottom" in first) or "formation" in first
    if has_header and not looks_like_refno(rows[0][0] if rows[0] else ""):
        h = rows[0]
        iref = find(["refno", "dblrefno", "wellid", "ref"], h) or 0
        itop = find(["top", "dbltop", "from", "strtop"], h)
        ibot = find(["bottom", "dblbottom", "to", "strbot"], h)
        iform = find(["formation", "strformation", "material", "lithology", "desc"], h)
        if None not in (itop, ibot, iform):
            return iref, itop, ibot, iform
        if len(h) >= 5:
            return 0, 2, 3, 4
        return 0, 1, 2, 3
    sample = rows[1 if has_header else 0] if rows else []
    if len(sample) >= 5 and looks_like_refno(sample[0]):
        return 0, 2, 3, 4
    return 0, 1, 2, 3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("litho_path")
    ap.add_argument("wells_csv", nargs="?", help="Wells CSV to add lithology_json (optional)")
    ap.add_argument("-o", "--output", help="Output wells CSV")
    ap.add_argument("--cols", help="refno,top,bottom,formation column indices 0-based")
    ap.add_argument("--parts-dir", default="litho_parts", help="Output dir for litho_N.json shards")
    ap.add_argument("--part-size", type=int, default=DEFAULT_PART, help="Shard size for refno bucketing (default: 1000)")
    args = ap.parse_args()
    part = int(args.part_size or DEFAULT_PART)
    if part <= 0:
        print("part-size must be > 0", file=sys.stderr)
        sys.exit(2)

    rows, delim = read_litho_rows(args.litho_path)
    if not rows:
        print("Empty litho.txt", file=sys.stderr)
        sys.exit(1)

    if args.cols:
        iref, itop, ibot, iform = [int(x.strip()) for x in args.cols.split(",")]
        try:
            int(float(rows[0][iref]))
            data_rows = rows
        except (ValueError, IndexError):
            data_rows = rows[1:]
    else:
        iref, itop, ibot, iform = detect_columns(rows)
        first = " ".join(normalize_header(c) for c in rows[0])
        has_header = ("top" in first and "bottom" in first) or (
            "formation" in first and not looks_like_refno(rows[0][0] if rows[0] else "")
        )
        data_rows = rows[1:] if has_header else rows

    by_ref = {}
    for row in data_rows:
        if len(row) <= max(iref, itop, ibot, iform):
            continue
        try:
            ref = int(float(str(row[iref]).strip().replace(",", "")))
        except (ValueError, TypeError):
            continue
        top = str(row[itop]).strip() if itop < len(row) else ""
        bot = str(row[ibot]).strip() if ibot < len(row) else ""
        form = str(row[iform]).strip() if iform < len(row) else ""
        by_ref.setdefault(ref, []).append({"top": top, "bottom": bot, "formation": form})

    for ref in by_ref:
        by_ref[ref].sort(key=lambda r: float(r["top"] or 0) if r["top"] else 0)

    os.makedirs(args.parts_dir, exist_ok=True)
    by_part = {}
    for ref, arr in by_ref.items():
        p = ref // part
        if p not in by_part:
            by_part[p] = {}
        by_part[p][str(ref)] = arr

    for p, obj in sorted(by_part.items()):
        path = os.path.join(args.parts_dir, "litho_%d.json" % p)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, separators=(",", ":"))
        print("  wrote %s (%d wells)" % (path, len(obj)))

    print("Lithology shards: %d files, %d wells total, part_size=%d delimiter=%s cols=%s,%s,%s,%s" % (
        len(by_part), len(by_ref), part, repr(delim), iref, itop, ibot, iform,
    ))

    if args.wells_csv and os.path.isfile(args.wells_csv):
        out_path = args.output or args.wells_csv
        with open(args.wells_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames or [])
            if "lithology_json" not in fieldnames:
                fieldnames.append("lithology_json")
            rows_out = []
            n = 0
            for row in reader:
                ref = row.get("refno") or row.get("ref_no") or ""
                try:
                    refi = int(float(str(ref).strip()))
                except (ValueError, TypeError):
                    refi = None
                if refi is not None and refi in by_ref:
                    row["lithology_json"] = json.dumps(by_ref[refi], separators=(",", ":"))
                    n += 1
                else:
                    row["lithology_json"] = ""
                rows_out.append(row)
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows_out)
        print("CSV %s — lithology_json on %d wells." % (out_path, n))
    else:
        print("(No wells CSV merge; litho_parts/ is enough for the app.)")


if __name__ == "__main__":
    main()
