#!/usr/bin/env python3
"""
Build statewide well data with well_bottom_elev from dnr_wells_full.csv
or dnr_wells_full.csv.gz (no decompress), plus lithology from one or more DNR WellLogs CSV/TXT files.
Outputs chunked gzipped CSVs for the web app.

Chunk column `aquifer` is filled from pass-through CSV fields if present, else inferred from
lithology + vein/rock + depth_bedrock (the DNR ArcGIS statewide layer has no aquifer-type text).

When registry depth (dbldepth) is blank, depth is filled for the viewer from (in order): deepest
WellLogs bottom interval; else casing_length + screen_length; else casing_length alone — same static
idea as lithology-driven g labels (see index getWellDisplayDepthFt).

Log files:
  • Default: all <this_folder>/well_logs_csv/*.{csv,txt} (and ~/Downloads/WellLogs_67952275.csv if the folder is empty)
  • Override: set DNR_LOGS_CSV_PATHS (or DNR_LOGS_CSV) — then ONLY those paths are used (no well_logs_csv scan)

County filter (lighter deploy, e.g. nine_counties.txt):
  • export DNR_COUNTIES_FILE=nine_counties.txt
  • Only wells whose county (from dnr_wells_full.csv) appears in that file (one name per line, # comments ok) are written to chunks.

100% lithology_json coverage (mandatory before chunks are written):
  • After WellLogs merge and optional HTML backfill, every row is checked: if lithology_json is missing,
    empty, invalid JSON, or has zero intervals, a depth-based single-interval record is written so the
    the static viewer and any downstream apps always have parseable logs (lithology_source becomes or stays `none` for that repair).
  • This is structural 100% coverage. For maximum *digitized* intervals from DNR’s website, also run:
      DNR_FILL_LITHO_HTML=1 DNR_HTML_LITHO_UNLIMITED=1
    (statewide; long-running; respects DNR_HTML_LITHO_DELAY; cache dnr_html_litho_cache.json).
    See run_full_lithology_html_statewide.sh in this repo.
  • Emergency only: DNR_SKIP_LITHO_100_GUARANTEE=1 skips the final guarantee pass (not recommended).

HTML lithology backfill (optional, for real tables where DNR published them):
  • export DNR_FILL_LITHO_HTML=1 — fetch DNR Details HTML for rows still missing lithology after WellLogs.
  • Statewide without DNR_COUNTIES_FILE: set DNR_HTML_LITHO_MAX=N or DNR_HTML_LITHO_UNLIMITED=1.
  • If a run cached network failures as empty: rm dnr_html_litho_cache.json or DNR_HTML_LITHO_REFRESH=1 once.

Modal fields (drill rig + method of testing) in chunks — HTML backfill:
  • Lithology HTML pass (DNR_FILL_LITHO_HTML=1) also parses drill_rig_type + test_method when it fetches Details HTML; stored in dnr_html_litho_cache.json and chunk columns.
  • Wells that already had CSV lithology: set DNR_FILL_MODAL_HTML=1 to fetch/merge meta only (same cache file).
  • Statewide: set DNR_MODAL_HTML_MAX=N or DNR_MODAL_HTML_UNLIMITED=1 (same idea as DNR_HTML_LITHO_*).
  • Clear only modal slots in cache: DNR_MODAL_HTML_REFRESH=1 (re-parse meta from HTML on next run).
  • If backfill gets zero parses: DNR may be serving a WAF page to Python — set DNR_HTTP_COOKIE from your
    browser’s request Cookie for secure.in.gov, try DNR_HTTP_MINIMAL_HEADERS=1, or DNR_HTML_DEBUG=1 (saves first HTML).
  • Put secrets in .env.local (see .env.example): keys are merged into os.environ before fetches (existing env wins).
  • If fetches fail with “Tunnel connection failed: 403”, your shell has HTTPS_PROXY set — run from Terminal without
    proxy or use run_dnr_fetch_no_proxy.sh / env -u HTTPS_PROXY -u HTTP_PROXY.
"""
import csv, json, gzip, os, math, re, sys
from collections import defaultdict

from dnr_csv_input import open_dnr_wells_csv_for_read, resolve_dnr_full_wells_csv
from dnr_env_local import ensure_dnr_env_local_loaded
from gravel_corrector import GravelVeinCorrector

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.environ.get("DNR_OUT_DIR", SCRIPT_DIR)
FULL_CSV_ENV = os.environ.get("DNR_FULL_CSV")
PUMP_CSV = os.environ.get("DNR_PUMP_CSV", os.path.join(OUT_DIR, "dnr_pump_rates.csv"))
CHUNK_SIZE = int(os.environ.get("DNR_CHUNK_SIZE", "50000"))
# Must match index.html DNR_CHUNK_PREFIX without the trailing underscore (files: {base}_0.csv.gz).
CHUNK_BASE = os.environ.get("DNR_CHUNK_FILE_PREFIX", "dnr_wells_chunk").strip().rstrip("_")

def safe_float(s):
    try: return float(s)
    except: return None

def val(row, key):
    return (row.get(key) or "").strip()

def normalize_ref_key(ref):
    """Match WellLogs RefNum to wells CSV refno (strip Excel floats / leading zeros)."""
    s = (ref or "").strip()
    if not s:
        return ""
    try:
        return str(int(float(s.replace(",", ""))))
    except ValueError:
        return s


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def infer_depth_ft_from_litho(litho: list) -> float | None:
    """Use deepest log bottom when registry depth is blank (same idea as g-label lithology)."""
    if not litho:
        return None
    max_b = 0.0
    saw_non_placeholder = False
    for row in litho:
        form = (row.get("formation") or "").lower()
        if "no digitized" in form or "dnr report" in form:
            continue
        saw_non_placeholder = True
        b = safe_float((row.get("bottom") or "").strip())
        if b is not None and b > max_b:
            max_b = b
    if not saw_non_placeholder or max_b < 5:
        return None
    return max_b


def infer_depth_ft_from_casing_screen(row: dict) -> float | None:
    if not row:
        return None
    cl = safe_float(str(row.get("casing_length") or "").strip())
    sl = safe_float(str(row.get("screen_length") or "").strip())
    if cl is not None and sl is not None and cl > 0 and sl > 0:
        return cl + sl
    if cl is not None and cl > 0:
        return cl
    return None


def apply_vein_from_litho(out_row: dict, litho: list, ref: str) -> None:
    """Recompute vein_size_ft / rock_start_ft / gravel_thickness_ft from lithology intervals."""
    out_row["vein_size_ft"] = ""
    out_row["rock_start_ft"] = ""
    out_row["gravel_thickness_ft"] = ""
    if not litho:
        return
    depth = safe_float(str(out_row.get("depth") or ""))
    construction = {
        "Depth": depth,
        "Well Depth": depth,
        "screen length": safe_float(str(out_row.get("screen_length") or "")),
        "screen (ft)": safe_float(str(out_row.get("screen_length") or "")),
        "screen length (ft)": safe_float(str(out_row.get("screen_length") or "")),
    }
    try:
        result = GravelVeinCorrector.correct_gravel_vein(
            {"construction": construction, "well_log": litho, "reference_number": ref}
        )
        vs = float(result.get("vein_size_ft") or 0)
        rs = float(result.get("rock_start_ft") or 0)
        if vs > 0:
            out_row["vein_size_ft"] = str(int(round(vs)))
            out_row["gravel_thickness_ft"] = out_row["vein_size_ft"]
        if rs > 0:
            out_row["rock_start_ft"] = str(int(round(rs)))
            if not out_row["gravel_thickness_ft"]:
                cap = depth if depth is not None and depth > 0 else rs
                col = min(rs, cap) if cap else rs
                out_row["gravel_thickness_ft"] = str(int(round(col)))
    except (TypeError, ValueError):
        pass


def g_registry_vein_to_rock_sane_vs_depth(g: float, depth: float | None) -> bool:
    """
    Registry bake: thickness to top of rock from depth_bedrock — must match viewer gBakedProductionVeinSaneVsDepth.
    Thick drift (high g/depth) is valid; only reject impossible geometry vs completed depth.
    """
    if g is None or g <= 0:
        return False
    if depth is None or depth <= 0:
        return True
    if g > depth + 0.5:
        return False
    if g >= depth:
        return False
    return True


def row_qualifies_for_registry_vein_bake(row: dict) -> bool:
    """
    Placeholder rows only: use registry depth_bedrock + completed depth — not inferred aquifer text.

    infer_chunk_aquifer often sets aquifer to \"Bedrock\" when depth > depth_bedrock + 2 ft (well bottoms in rock).
    The old row_is_unconsolidated check treated dep > db as \"not gravel\" and skipped bake entirely, so **0** rows
    got registry vein despite valid overburden thickness min(depth_bedrock, depth).
    """
    dep = safe_float(str(row.get("depth") or ""))
    db = safe_float(str(row.get("depth_bedrock") or ""))
    if db is None or db <= 0 or dep is None or dep <= 0:
        return False
    if dep + 0.5 < db:
        return False
    return True


def bake_registry_vein_for_placeholder_rows(out_rows: list) -> int:
    """
    Fill vein_size_ft / gravel_thickness_ft from depth_bedrock when lithology_source is still ``none`` (placeholder
    interval only), registry has depth_to_bedrock, and min(depth_bedrock, depth) passes viewer-style sanity.
    Static in chunks — viewer reads vein_size_ft via getProductionVeinSizeFtFromCsv (no full-depth fallback).
    """
    n_baked = 0
    for row in out_rows:
        if str(row.get("vein_size_ft") or "").strip():
            continue
        if str(row.get("lithology_source") or "").strip().lower() != "none":
            continue
        if not row_qualifies_for_registry_vein_bake(row):
            continue
        dep = safe_float(str(row.get("depth") or ""))
        db = safe_float(str(row.get("depth_bedrock") or ""))
        if not (db and db > 0):
            continue
        if not (dep and dep > 0):
            continue
        # Thickness to top of rock, capped by completed depth (same idea as viewer drift).
        g_cand = min(db, dep)
        if not g_registry_vein_to_rock_sane_vs_depth(g_cand, dep):
            continue
        gi = int(round(g_cand))
        if gi <= 0:
            continue
        row["vein_size_ft"] = str(gi)
        row["gravel_thickness_ft"] = str(gi)
        row["rock_start_ft"] = str(int(round(db)))
        n_baked += 1
    return n_baked


def _parse_positive_int_depth(v) -> int | None:
    if v is None or v == "":
        return None
    try:
        n = int(round(float(str(v).replace(",", "").strip())))
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def _litho_interval_tb(
    layer: dict, prev_bottom: float
) -> tuple[float, float] | None:
    o = layer if isinstance(layer, dict) else {}

    def pf(x) -> float:
        try:
            return float(str(x).replace(",", "").strip())
        except (TypeError, ValueError):
            return float("nan")

    top = pf(
        o.get("top")
        or o.get("Top")
        or o.get("from")
        or o.get("From")
        or ""
    )
    bot = pf(
        o.get("bottom")
        or o.get("Bottom")
        or o.get("to")
        or o.get("To")
        or ""
    )
    if math.isnan(top) and not math.isnan(prev_bottom):
        top = prev_bottom
    if math.isnan(top) or math.isnan(bot) or bot <= top:
        return None
    return top, bot


_SGRP = re.compile(
    r"grav|gravel|\bsand\b|\bsa\b|\bgr\b|\bsg\b|drift|outwash|till|alluv|terrace|esker|kame|muck|topsoil|loess|"
    r"coarse\s*sand|fine\s*sand|medium\s*sand|dirty\s*grav|sandy\s*grav",
    re.I,
)
_ROCKISH = re.compile(
    r"lime|dolomite|shale|slate|bedrock|sandstone|siltstone|granite|marble|chert|quartzite|basalt|"
    r"gneiss|schist|conglomerate|argillite|\b(ls|lm|dl)\b",
    re.I,
)


def litho_sand_gravel_intervals_ge_1ft(litho: list) -> int:
    n = 0
    prev = float("nan")
    for layer in litho:
        if not isinstance(layer, dict):
            continue
        fm = str(layer.get("formation") or layer.get("Formation") or "").strip()
        tb = _litho_interval_tb(layer, prev)
        if tb is None:
            continue
        top, bot = tb
        prev = bot
        if bot - top < 1:
            continue
        if not _SGRP.search(fm):
            continue
        if _ROCKISH.search(fm) and not re.search(
            r"sand|grav|drift|alluv|till|outwash", fm, re.I
        ):
            continue
        n += 1
    return n


def _aquifer_from_last_litho_formation(litho: list) -> str:
    if not litho:
        return ""
    last = str(litho[-1].get("formation") or litho[-1].get("Formation") or "").lower()
    if not last.strip():
        return ""
    if "no digitized" in last or "dnr report" in last:
        return ""
    # "sandstone"/"siltstone"/"quartzite" match r"sand" — classify as bedrock unless strong drift/gravel cues.
    if re.search(r"\bsandstone\b|\bsiltstone\b|\bquartzite\b", last, re.I):
        if not re.search(
            r"grav|gravel|drift|outwash|till|alluv|glacial|sand\s+and\s+grav",
            last,
            re.I,
        ):
            return "Bedrock"
    has_sand = bool(
        re.search(
            r"sand|grav|drift|fill|till|outwash|alluv|esker|kame|muck|topsoil|loess|silty|loam",
            last,
        )
    )
    has_rock = bool(_ROCKISH.search(last))
    if has_sand and (not has_rock or re.search(r"sand|grav|drift", last)):
        return "Unconsolidated"
    if has_rock and not re.search(r"sand|grav|drift|fill|till", last):
        return "Bedrock"
    return ""


def infer_chunk_aquifer(
    csv_row: dict | None,
    litho: list,
    depth_int: int | None,
    depth_bedrock_registry: float | None,
    out_row: dict,
) -> str:
    """
    Viewer + hub expect an `aquifer` string. The DNR ArcGIS statewide layer has no aquifer-type field;
    use pass-through columns if present on the source CSV, else infer (aligned with hub area insights).
    """
    if csv_row:
        direct = (
            val(csv_row, "aquifer")
            or val(csv_row, "primary_aquifer")
            or val(csv_row, "water_bearing_formation")
            or val(csv_row, "aquifer_type")
        ).strip()
        if direct:
            return direct[:200]
    loc = (
        val(csv_row, "loc_type")
        if csv_row
        else str(out_row.get("loc_type") or "").strip()
    ).lower()
    if "estimated" in loc:
        return "Estimated"
    vs = safe_float(str(out_row.get("vein_size_ft") or ""))
    gt = safe_float(str(out_row.get("gravel_thickness_ft") or ""))
    if (vs is not None and vs >= 1) or (gt is not None and gt >= 1):
        return "Unconsolidated"
    d_br = depth_bedrock_registry
    if csv_row is None:
        d_br = safe_float(str(out_row.get("depth_bedrock") or ""))
    if d_br is not None and d_br > 0 and depth_int is not None and depth_int > d_br + 2:
        return "Bedrock"
    rs = safe_float(str(out_row.get("rock_start_ft") or ""))
    if rs is not None and rs > 0 and depth_int is not None and depth_int > rs + 2:
        return "Bedrock"
    if litho_sand_gravel_intervals_ge_1ft(litho) >= 1:
        return "Unconsolidated"
    lab = _aquifer_from_last_litho_formation(litho)
    if lab:
        return lab
    return ""


def lithology_json_has_at_least_one_interval(raw) -> bool:
    """True if JSON parses to a non-empty interval list (same shapes as hub/viewer)."""
    s = str(raw or "").strip()
    if not s or s in ("{}", "[]", "null", '""'):
        return False
    try:
        j = json.loads(s)
        if isinstance(j, str):
            inner = j.strip()
            if inner.startswith("[") or inner.startswith("{"):
                j = json.loads(inner)
        if isinstance(j, list):
            return len(j) > 0
        if isinstance(j, dict):
            for key in (
                "layers",
                "intervals",
                "data",
                "well_log",
                "WellLog",
                "Lithology",
                "records",
            ):
                a = j.get(key)
                if isinstance(a, list) and len(a) > 0:
                    return True
        return False
    except (json.JSONDecodeError, TypeError, ValueError):
        return False


def apply_depth_placeholder_lithology_row(row: dict) -> list:
    """
    Single-interval placeholder so parsers never see an empty log.
    Returns the list used for vein + aquifer refresh.
    """
    d = row.get("depth")
    try:
        bd = int(float(d))
        if bd < 1:
            bd = 1
    except (TypeError, ValueError):
        bd = 1
    ph = [
        {
            "top": "0",
            "bottom": str(bd),
            "formation": (
                "(No digitized table in merged WellLogs — open DNR report for log/PDF; "
                "rebuild with DNR_FILL_LITHO_HTML=1 to attempt HTML table extract)"
            ),
        }
    ]
    row["lithology_json"] = json.dumps(ph, separators=(",", ":"))
    src = str(row.get("lithology_source") or "").strip()
    if src not in ("csv", "html"):
        row["lithology_source"] = "none"
    ref = str(row.get("refno") or "")
    apply_vein_from_litho(row, ph, ref)
    d_int = _parse_positive_int_depth(row.get("depth"))
    d_br = safe_float(str(row.get("depth_bedrock") or ""))
    row["aquifer"] = infer_chunk_aquifer(None, ph, d_int, d_br, row)
    return ph


def ensure_one_hundred_percent_lithology_json(out_rows: list) -> int:
    """
    Every output row must have lithology_json with ≥1 interval before gz chunks are written.
    Returns the number of rows that required a placeholder repair.
    """
    n_fixed = 0
    for row in out_rows:
        if lithology_json_has_at_least_one_interval(row.get("lithology_json")):
            continue
        apply_depth_placeholder_lithology_row(row)
        n_fixed += 1
    return n_fixed


def load_county_allow_set(script_dir):
    """Uppercase county names from DNR_COUNTIES_FILE, or None if unset."""
    raw = (os.environ.get("DNR_COUNTIES_FILE") or "").strip()
    if not raw:
        return None
    path = raw if os.path.isabs(raw) else os.path.join(script_dir, raw)
    if not os.path.isfile(path):
        print(f"  ERROR: DNR_COUNTIES_FILE not found: {path}", file=sys.stderr)
        sys.exit(1)
    out = set()
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.split("#", 1)[0].strip()
            if s:
                out.add(s.upper())
    if not out:
        print("  ERROR: county filter file is empty", file=sys.stderr)
        sys.exit(1)
    print(f"  County filter: {len(out)} names from {os.path.basename(path)} — only those wells go to chunks")
    return out

def _norm_header(h):
    return (h or "").strip().lstrip("\ufeff").lower().replace(" ", "")

def discover_log_csv_paths(out_dir):
    """Resolve WellLogs files. If DNR_LOGS_CSV_PATHS or DNR_LOGS_CSV is non-empty, use only those
    files (and do not scan well_logs_csv/). Otherwise scan well_logs_csv/* and optional default Download."""
    paths: list[str] = []
    envp = (os.environ.get("DNR_LOGS_CSV_PATHS") or os.environ.get("DNR_LOGS_CSV") or "").strip()
    env_exclusive = bool(envp)
    if envp:
        for part in envp.replace(";", os.pathsep).split(os.pathsep):
            p = os.path.expanduser(part.strip().strip('"').strip("'"))
            if p and os.path.isfile(p):
                paths.append(p)
    else:
        well_logs_dir = os.path.join(out_dir, "well_logs_csv")
        if os.path.isdir(well_logs_dir):
            for fn in sorted(os.listdir(well_logs_dir)):
                if fn.startswith("."):
                    continue
                low = fn.lower()
                if low.endswith((".csv", ".txt")):
                    # Skip docs / placeholders — not DNR WellLogs (avoids README.txt warnings).
                    if low.startswith("readme") or low in (".gitkeep", "license", "license.txt"):
                        continue
                    paths.append(os.path.join(well_logs_dir, fn))
        default_dl = os.path.expanduser("~/Downloads/WellLogs_67952275.csv")
        if not paths and os.path.isfile(default_dl):
            paths = [default_dl]
    seen: set[str] = set()
    uniq: list[str] = []
    for p in paths:
        rp = os.path.realpath(p)
        if rp not in seen:
            seen.add(rp)
            uniq.append(p)
    if env_exclusive and not uniq:
        print(
            "  WARNING: DNR_LOGS_CSV_PATHS is set but no log files were found — check paths.",
            file=sys.stderr,
        )
    elif env_exclusive and uniq:
        print(
            f"  NOTE: DNR_LOGS_CSV_PATHS set — loading only {len(uniq)} file(s); well_logs_csv/ is NOT scanned. "
            "Unset both vars to merge all CSVs under well_logs_csv/.",
            file=sys.stderr,
        )
    return uniq

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
                ref = normalize_ref_key(ref)
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
    ensure_dnr_env_local_loaded()
    print(f"  build_statewide_data.py (enriched chunks): {os.path.abspath(__file__)}")
    full_csv = resolve_dnr_full_wells_csv(OUT_DIR, FULL_CSV_ENV)
    print(f"  DNR_OUT_DIR={OUT_DIR!r}  wells_input={full_csv!r}")
    # 1. Load lithology from all discovered log files
    log_paths = discover_log_csv_paths(OUT_DIR)
    print("Loading well lithology logs...")
    logs = defaultdict(list)
    total_intervals = 0
    if not log_paths:
        print("  WARNING: No log files. Add CSV/TXT under well_logs_csv/, or set DNR_LOGS_CSV_PATHS to explicit file paths.")
    for p in log_paths:
        n = append_logs_from_file(p, logs)
        total_intervals += n
        print(f"  {os.path.basename(p)}: {n:,} intervals")
    for ref in logs:
        logs[ref].sort(key=lambda x: safe_float(x["top"]) or 0)
    print(f"  {len(logs):,} unique wells with lithology ({total_intervals:,} intervals total)")

    # 2. Load statewide pump rates (optional file)
    print("Loading statewide pump rates...")
    pump_rates = {}
    if os.path.isfile(PUMP_CSV):
        with open(PUMP_CSV, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                ref = normalize_ref_key((row.get("refno") or "").strip())
                pr = safe_float((row.get("pump_rate") or "").strip())
                if ref and pr is not None and pr > 0:
                    pump_rates[ref] = pr
        print(f"  {len(pump_rates):,} wells with pump rates")
    else:
        print(f"  WARNING: {PUMP_CSV} not found — pump_rate will be empty (build continues)")

    # 3. Process full statewide CSV (optional county filter)
    county_allow = load_county_allow_set(SCRIPT_DIR)
    print("Processing statewide wells...")
    out_rows = []
    calc_count = 0
    depth_inferred_count = 0
    skip_no_coords = 0
    skip_county = 0

    fields = ["id", "refno", "lat", "lon", "depth", "county", "owner", "report",
              "loc_type", "aquifer", "ground_elev", "well_bottom_elev", "static_water",
              "depth_bedrock", "well_use", "casing_material", "casing_diam",
              "casing_length", "screen_diam", "screen_length", "pump_type",
              "pump_rate", "bailer_rate", "vein_size_ft", "rock_start_ft", "gravel_thickness_ft",
              "lithology_json", "lithology_source", "drill_rig_type", "test_method"]

    with open_dnr_wells_csv_for_read(full_csv) as f:
        for row in csv.DictReader(f):
            ref = normalize_ref_key(val(row, "refno"))
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

            if county_allow is not None:
                co = val(row, "county").upper()
                if co not in county_allow:
                    skip_county += 1
                    continue

            ground_elev = safe_float(val(row, "ground_elev"))
            depth_csv = safe_float(val(row, "depth"))

            litho = logs.get(ref, [])
            litho_json = json.dumps(litho, separators=(",", ":")) if litho else ""
            lithology_source = "csv" if litho else ""

            depth_work = depth_csv if depth_csv is not None and depth_csv > 0 else None
            if depth_work is None:
                depth_work = infer_depth_ft_from_litho(litho)
            if depth_work is None:
                depth_work = infer_depth_ft_from_casing_screen(
                    {"casing_length": val(row, "casing_length"), "screen_length": val(row, "screen_length")}
                )
            depth_int = int(round(depth_work)) if depth_work is not None and depth_work > 0 else None
            if depth_int is not None and (depth_csv is None or depth_csv <= 0):
                depth_inferred_count += 1

            well_bottom_elev = None
            if ground_elev is not None and depth_int is not None and depth_int > 0:
                well_bottom_elev = round(ground_elev - depth_int)
                calc_count += 1

            report = val(row, "report")
            if not report and ref:
                report = f"https://secure.in.gov/apps/dnr/water/dnr_waterwell?refNo={ref}&_from=SUMMARY&_action=Details"

            depth_bedrock = safe_float(val(row, "depth_bedrock"))

            pr_csv = safe_float(val(row, "pump_rate"))
            pr_file = pump_rates.get(ref)
            pr_merge = pr_csv if pr_csv is not None and pr_csv > 0 else None
            if pr_merge is None and pr_file is not None:
                try:
                    pr_merge = float(pr_file)
                except (TypeError, ValueError):
                    pr_merge = None
            if pr_merge is not None and pr_merge <= 0:
                pr_merge = None
            br_csv = safe_float(val(row, "bailer_rate"))
            br_out = br_csv if br_csv is not None and br_csv > 0 else None

            out_row = {
                "id": val(row, "id") or f"DNR-{ref}",
                "refno": ref,
                "lat": lat,
                "lon": lon,
                "depth": depth_int if depth_int is not None else "",
                "county": val(row, "county"),
                "owner": val(row, "owner"),
                "report": report,
                "loc_type": val(row, "loc_type"),
                "ground_elev": int(ground_elev) if ground_elev is not None else "",
                "well_bottom_elev": well_bottom_elev if well_bottom_elev is not None else "",
                "static_water": val(row, "static_water"),
                "depth_bedrock": int(depth_bedrock) if depth_bedrock is not None else "",
                "well_use": val(row, "well_use") or val(row, "welluse") or "",
                "casing_material": val(row, "casing_material"),
                "casing_diam": val(row, "casing_diam"),
                "casing_length": val(row, "casing_length"),
                "screen_diam": val(row, "screen_diam"),
                "screen_length": val(row, "screen_length"),
                "pump_type": val(row, "pump_type"),
                "pump_rate": (str(int(pr_merge)) if pr_merge is not None and pr_merge == int(pr_merge) else (str(pr_merge) if pr_merge is not None else "")),
                "bailer_rate": (str(int(br_out)) if br_out is not None and br_out == int(br_out) else (str(br_out) if br_out is not None else "")),
                "vein_size_ft": "",
                "rock_start_ft": "",
                "gravel_thickness_ft": "",
                "lithology_json": litho_json,
                "lithology_source": lithology_source,
                "drill_rig_type": "",
                "test_method": "",
            }
            apply_vein_from_litho(out_row, litho, ref)
            out_row["aquifer"] = infer_chunk_aquifer(
                row, litho, depth_int, depth_bedrock, out_row
            )
            out_rows.append(out_row)

            if len(out_rows) % 100000 == 0:
                print(f"  ...{len(out_rows):,} wells processed")

    print(f"  {len(out_rows):,} wells with coordinates")
    print(f"  {skip_no_coords:,} skipped (no coords)")
    if county_allow is not None:
        print(f"  {skip_county:,} skipped (county not in filter)")
    print(f"  {calc_count:,} with pre-computed well bottom elevation")
    print(f"  {depth_inferred_count:,} with depth filled from litho max / casing (+ screen) where registry blank")
    litho_count = sum(1 for r in out_rows if r["lithology_json"])
    print(f"  {litho_count:,} with non-empty lithology_json after WellLogs merge (before 100% guarantee)")
    g_ready = sum(
        1 for r in out_rows
        if (r.get("vein_size_ft") or r.get("rock_start_ft") or r.get("gravel_thickness_ft"))
    )
    print(f"  {g_ready:,} rows with vein/rock CSV columns (g-label ready)")
    aq_n = sum(1 for r in out_rows if str(r.get("aquifer") or "").strip())
    print(f"  {aq_n:,} rows with non-empty aquifer (pass-through or inferred)")

    if _env_truthy("DNR_FILL_LITHO_HTML"):
        from dnr_report_html_lithology import fill_rows_from_dnr_html

        n_missing = sum(1 for r in out_rows if not (r.get("lithology_json") or "").strip())
        if n_missing == 0:
            print("  HTML lithology backfill: 0 rows missing (skip)")
        else:
            delay = float(os.environ.get("DNR_HTML_LITHO_DELAY", "0.18") or 0.18)
            max_fetches = None
            if county_allow is None:
                if _env_truthy("DNR_HTML_LITHO_UNLIMITED"):
                    max_fetches = None
                else:
                    raw_max = (os.environ.get("DNR_HTML_LITHO_MAX") or "").strip()
                    if raw_max:
                        max_fetches = int(raw_max)
                    else:
                        print(
                            "  SKIP HTML lithology backfill: statewide build (no DNR_COUNTIES_FILE) "
                            "needs DNR_HTML_LITHO_MAX=N or DNR_HTML_LITHO_UNLIMITED=1",
                            file=sys.stderr,
                        )
                        max_fetches = -1
            if max_fetches != -1:
                print(
                    f"  HTML lithology backfill: {n_missing:,} rows missing — "
                    f"delay {delay}s, cache {os.path.join(OUT_DIR, 'dnr_html_litho_cache.json')} "
                    f"(progress every {max(1, int(os.environ.get('DNR_HTML_LITHO_PROGRESS', '25') or '25'))} rows)"
                )

                def html_fill_apply(
                    row: dict, litho_list: list, source: str, meta: dict | None = None
                ) -> None:
                    meta = meta or {}
                    for k in ("drill_rig_type", "test_method"):
                        v = str(meta.get(k) or "").strip()
                        if v and not str(row.get(k) or "").strip():
                            row[k] = v
                    litho_for_aq: list = []
                    if source == "html" and litho_list:
                        row["lithology_json"] = json.dumps(litho_list, separators=(",", ":"))
                        row["lithology_source"] = "html"
                        litho_for_aq = litho_list
                        apply_vein_from_litho(row, litho_list, str(row.get("refno") or ""))
                    else:
                        d = row.get("depth")
                        try:
                            bd = int(float(d))
                            if bd < 1:
                                bd = 1
                        except (TypeError, ValueError):
                            bd = 1
                        ph = [
                            {
                                "top": "0",
                                "bottom": str(bd),
                                "formation": "(No digitized table — open DNR report for log/PDF)",
                            }
                        ]
                        litho_for_aq = ph
                        row["lithology_json"] = json.dumps(ph, separators=(",", ":"))
                        row["lithology_source"] = "none"
                        apply_vein_from_litho(row, ph, str(row.get("refno") or ""))
                    d_int = _parse_positive_int_depth(row.get("depth"))
                    d_br = safe_float(str(row.get("depth_bedrock") or ""))
                    row["aquifer"] = infer_chunk_aquifer(
                        None, litho_for_aq, d_int, d_br, row
                    )

                nh, nph, ncap, nmeta = fill_rows_from_dnr_html(
                    out_rows,
                    out_dir=OUT_DIR,
                    delay_sec=delay,
                    max_fetches=max_fetches,
                    apply_fn=html_fill_apply,
                )
                print(
                    f"  HTML backfill done: log_table_from_html={nh:,} "
                    f"drill_or_method_only={nmeta:,} placeholder={nph:,} capped_no_fetch={ncap:,}"
                )
                litho_count2 = sum(1 for r in out_rows if r.get("lithology_json"))
                print(f"  {litho_count2:,} with non-empty lithology_json after backfill")
                src_csv = sum(1 for r in out_rows if r.get("lithology_source") == "csv")
                src_html = sum(1 for r in out_rows if r.get("lithology_source") == "html")
                src_none = sum(1 for r in out_rows if r.get("lithology_source") == "none")
                print(f"  lithology_source: csv={src_csv:,} html={src_html:,} none={src_none:,} (none=placeholder only)")
                g_ready = sum(
                    1 for r in out_rows
                    if (r.get("vein_size_ft") or r.get("rock_start_ft") or r.get("gravel_thickness_ft"))
                )
                print(f"  {g_ready:,} rows with vein/rock columns after HTML backfill")

    if _env_truthy("DNR_FILL_MODAL_HTML"):
        from dnr_report_html_lithology import fill_modal_meta_from_dnr_html

        n_need = sum(
            1
            for r in out_rows
            if (not str(r.get("drill_rig_type") or "").strip())
            or (not str(r.get("test_method") or "").strip())
        )
        if n_need == 0:
            print("  HTML modal-meta backfill: 0 rows need drill/method (skip)")
        else:
            delay_m = float(
                os.environ.get("DNR_MODAL_HTML_DELAY")
                or os.environ.get("DNR_HTML_LITHO_DELAY", "0.18")
                or "0.18"
            )
            max_modal: int | None = None
            if county_allow is None:
                if _env_truthy("DNR_MODAL_HTML_UNLIMITED"):
                    max_modal = None
                else:
                    raw_mm = (os.environ.get("DNR_MODAL_HTML_MAX") or "").strip()
                    if raw_mm:
                        max_modal = int(raw_mm)
                    else:
                        print(
                            "  SKIP modal-meta backfill: statewide (no DNR_COUNTIES_FILE) "
                            "needs DNR_MODAL_HTML_MAX=N or DNR_MODAL_HTML_UNLIMITED=1",
                            file=sys.stderr,
                        )
                        max_modal = -1
            if max_modal != -1:
                print(
                    f"  HTML modal-meta backfill: up to {n_need:,} rows — delay {delay_m}s, "
                    f"cache {os.path.join(OUT_DIR, 'dnr_html_litho_cache.json')}"
                )
                mu, mmiss, mcap = fill_modal_meta_from_dnr_html(
                    out_rows,
                    out_dir=OUT_DIR,
                    delay_sec=delay_m,
                    max_fetches=max_modal,
                )
                print(
                    f"  Modal-meta done: apply_ops={mu:,} still_missing_rows≈{mmiss:,} capped_no_fetch={mcap:,}"
                )
                dr_n = sum(1 for r in out_rows if str(r.get("drill_rig_type") or "").strip())
                tm_n = sum(1 for r in out_rows if str(r.get("test_method") or "").strip())
                print(f"  {dr_n:,} rows with drill_rig_type, {tm_n:,} with test_method")

    if not _env_truthy("DNR_SKIP_LITHO_100_GUARANTEE"):
        n_pad = ensure_one_hundred_percent_lithology_json(out_rows)
        total = len(out_rows)
        print(
            f"\n  Lithology 100% guarantee: {total:,} rows have ≥1 interval "
            f"({n_pad:,} required depth-based placeholder repair)."
        )
        src_csv = sum(1 for r in out_rows if r.get("lithology_source") == "csv")
        src_html = sum(1 for r in out_rows if r.get("lithology_source") == "html")
        src_none = sum(1 for r in out_rows if r.get("lithology_source") == "none")
        print(
            f"  lithology_source after guarantee: csv={src_csv:,} html={src_html:,} none={src_none:,}"
        )
    else:
        print(
            "\n  WARNING: DNR_SKIP_LITHO_100_GUARANTEE=1 — chunks may contain empty lithology_json.",
            file=sys.stderr,
        )

    n_baked_vein = bake_registry_vein_for_placeholder_rows(out_rows)
    print(
        f"  Registry vein bake (placeholder lith + uncon + depth_bedrock): {n_baked_vein:,} rows"
    )

    def _n_positive(col: str) -> int:
        n = 0
        for r in out_rows:
            v = safe_float(str(r.get(col) or ""))
            if v is not None and v > 0:
                n += 1
        return n

    n_vs = _n_positive("vein_size_ft")
    n_rs = _n_positive("rock_start_ft")
    n_gf = _n_positive("gravel_thickness_ft")
    head = out_rows[:CHUNK_SIZE]
    n_vs_c0 = sum(
        1
        for r in head
        if (v := safe_float(str(r.get("vein_size_ft") or ""))) is not None and v > 0
    )
    print(
        f"  Chunk input totals: vein_size_ft>0: {n_vs:,}, rock_start_ft>0: {n_rs:,}, "
        f"gravel_thickness_ft>0: {n_gf:,}"
    )
    print(
        f"  First chunk only (rows 0–{CHUNK_SIZE - 1}): vein_size_ft>0: {n_vs_c0:,} "
        f"— verify_vein_g_production.py default scans chunk 0; use --all-chunks for statewide."
    )

    # 4. Write chunks
    print(f"\nWriting chunks of {CHUNK_SIZE:,} (prefix {CHUNK_BASE}_)...")
    total_raw = 0
    total_gz = 0
    chunk_idx = 0

    chunk_pat = re.compile(
        r"^(" + re.escape(CHUNK_BASE) + r"_|statewide_wells_chunk_)\d+\.csv\.gz$"
    )
    for old in os.listdir(OUT_DIR):
        if not chunk_pat.match(old):
            continue
        try:
            os.remove(os.path.join(OUT_DIR, old))
        except OSError:
            pass

    for start in range(0, len(out_rows), CHUNK_SIZE):
        chunk = out_rows[start:start + CHUNK_SIZE]
        csv_path = os.path.join(OUT_DIR, f"{CHUNK_BASE}_{chunk_idx}.csv")
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
