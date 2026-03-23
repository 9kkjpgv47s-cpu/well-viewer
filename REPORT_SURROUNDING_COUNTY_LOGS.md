# Report: Why surrounding-county well logs “won’t upload” & what we changed

## Executive summary

“Upload” breaks for **three different reasons** depending on what you mean:

1. **Vercel / production site** — Raw `.txt` / `.csv` log files are **intentionally excluded** from deployment (`.vercelignore`). The browser app never receives them. You must **run the Python build locally** to bake lithology into `statewide_wells_chunk_*.csv.gz`, then deploy.

2. **Different computer / Cursor / IDE** — Scripts used **hardcoded paths** like `/Users/dominiceasterling/Downloads/WellLogs_....csv`. On another machine that path **does not exist** → `FileNotFoundError` or silent “no logs.”

3. **`build_other_counties.py`** — It did `from gravel_corrector import GravelVeinCorrector` but **`gravel_corrector.py` was missing** → immediate `ImportError`, so that pipeline never ran.

**File format:** DNR “WellLogs” are usually **CSV** (sometimes saved as `.txt` with **tabs**). They must have a **header row** and columns that identify **well ref**, **depth interval**, and **formation** (we map common name variants).

---

## Approach (how lithology gets into the app)

1. **Local ETL only** — `build_statewide_data.py` reads `dnr_wells_full.csv` + one or more log files, writes `lithology_json` per well, outputs gzipped chunks.

2. **Multi-county logs** — All matching files under `well_logs_csv/` (or paths in `DNR_LOGS_CSV_PATHS`) are **merged** into one `logs[ref]` dictionary (same `refno` as statewide CSV).

3. **Deploy** — Only **`statewide_wells_chunk_*.csv.gz`** (not ignored by `.vercelignore`) ships with the site; the HTML loader fetches those chunks.

---

## Code changed (this session)

| File | Change |
|------|--------|
| **`gravel_corrector.py`** | **NEW.** Implements `GravelVeinCorrector.correct_gravel_vein()` for `build_other_counties.py` (dict-based lithology rows). |
| **`build_statewide_data.py`** | **Paths:** `OUT_DIR` / `FULL_CSV` / `PUMP_CSV` default to script directory + env overrides. **Logs:** `discover_log_csv_paths()` loads `well_logs_csv/*.{csv,txt}` and/or `DNR_LOGS_CSV_PATHS` / `DNR_LOGS_CSV`. **Parsing:** `append_logs_from_file()` auto-detects **comma vs tab**, flexible column names (RefNum/RefNo, From/To, Formation, etc.). |
| **`build_other_counties.py`** | `OUT_DIR` set to **script directory** instead of a fixed user home path. |
| **`well_logs_csv/README.txt`** | **NEW.** Instructions for where to drop exports and how to rebuild. |
| **`REPORT_SURROUNDING_COUNTY_LOGS.md`** | **NEW.** This report. |

*(No change to `C&J Well Viewer.html` in this task — viewer already reads `lithology_json` from chunks.)*

---

## Checklist: make surrounding counties work

1. Export **WellLogs** from DNR (CSV or tabbed TXT) for each county.
2. Copy into **`DNR_Well_Viewer_Full_Demo/well_logs_csv/`** (or set `DNR_LOGS_CSV_PATHS`).
3. Confirm header includes something like **RefNum** + **From/To** (or Top/Bottom) + **Formation**.
4. On **your Mac**, run:
   ```bash
   cd ~/DNR_Well_Viewer_Full_Demo && python3 build_statewide_data.py
   ```
5. Deploy:
   ```bash
   cd ~/DNR_Well_Viewer_Full_Demo && vercel --prod
   ```

---

## If it still fails

| Symptom | Likely cause |
|--------|----------------|
| `ImportError: gravel_corrector` | Pull latest repo; `gravel_corrector.py` must exist next to `build_other_counties.py`. |
| `No log files` warning | Empty `well_logs_csv/` and no `~/Downloads/WellLogs_67952275.csv` — add files or set `DNR_LOGS_CSV_PATHS`. |
| `need RefNum + To/Bottom columns` | File is not DNR WellLogs shape, or wrong delimiter — open in a spreadsheet and fix header names. |
| Logs on Vercel but app unchanged | `.vercelignore` blocks raw logs — you must rebuild chunks locally and redeploy. |
| Chunk too large for Vercel | Use external hosting for chunks (`DNR_CHUNK_BASE_URL` in HTML) or increase chunk count / slim columns (see `HOST_CHUNKS_OFF_VERCEL.txt`). |

---

## Terminal command (rebuild + deploy)

```bash
cd ~/DNR_Well_Viewer_Full_Demo && python3 build_statewide_data.py && vercel --prod
```
