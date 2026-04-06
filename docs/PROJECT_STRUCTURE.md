# DNR Well Viewer — project structure

Static single-page app + Python data pipeline. Primary user-facing artifact: **`index.html`** at repo root (Vercel / `python3 -m http.server`).

## Layout (high level)

| Path | Role |
|------|------|
| **`index.html`** | Full app: UI, Leaflet map, Papa Parse chunk loader, all **g/r** logic, filters, modal DNR report behavior. ~2700 lines inline JS. |
| **`dnr_wells_chunk_{0..N}.csv.gz`** | Runtime data (not in git if large); must sit **next to** `index.html` for default fetch URLs. |
| **`build_statewide_data.py`** | Canonical chunk builder: reads `dnr_wells_full.csv`, merges WellLogs, infers `aquifer`, `vein_size_ft`, **forces non-empty `lithology_json`** on every row, writes gz chunks. |
| **`rebuild_viewer_data.py`** | Orchestrator: runs `build_statewide_data.py`, verifies headers, runs `verify_vein_g_production.py`. |
| **`gravel_corrector.py`** | `GravelVeinCorrector` — computes `vein_size_ft` / `rock_start_ft` from interval list + screen overlap heuristic. |
| **`verify_vein_g_production.py`** | Post-build stats over chunks (vein columns, optional `--all-chunks`). |
| **`dnr_env_local.py`** | Loads optional `.env.local` into `os.environ` (secrets for HTML fetch, etc.). |
| **`chunk_dnr_csv.py`** | **Legacy splitter**: shuffles rows from a CSV into chunks **without** enriched columns — **not** equivalent to `build_statewide_data.py`. |
| **`fetch_dnr_wells.py`**, **`fetch_pump_rates.py`** | Acquire / refresh source CSVs. |
| **`api/dnr-report.js`** | Vercel serverless: DNR report HTML for modal when running on HTTPS. |
| **`C&J Well Viewer.html`**, **`1 - OPEN_ME_DNR_Viewer.html`** | Alternate / older entry points — risk of **diverging** from `index.html`. |

## Runtime dependency graph (browser)

```
index.html
  ├── CDN: Leaflet, leaflet.markercluster, Papa Parse
  ├── fetch(dnr_wells_chunk_i.csv.gz) × N
  ├── normalizeCsvRow → well objects (lowercased keys + lithology_json)
  └── refreshMap → DivIcon markers (combo vs dot) + filters
```

## Data dependency graph (Python)

```
dnr_wells_full.csv + well_logs_csv/*.csv [+ optional HTML backfill]
  → build_statewide_data.main()
  → out_rows[] with aquifer, vein_*, lithology_json, lithology_source
  → gzip chunks
```

## Chunk schema (enriched)

Expected by **`rebuild_viewer_data.verify_chunk0`** and viewer: at least **`refno`, `lat`, `lon`, `aquifer`, `vein_size_ft`, `lithology_json`**.

## Viewer load contract

- **`dnrChunkExpected`** in `index.html` must equal the number of chunk files (currently **9** for ~415k wells @ 50k/chunk).
- **`window.CJ_DNR_CHUNK_COUNT`** can override before scripts run.
- Wrong count → missing tail chunk or extra 404s.

## Related repos

- **`well-driller-dash-board`** (Hub): separate TS (`viewer-well-map.ts`) + embedded `public/well-viewer/index.html` — **not automatically synced** with this demo; parity is manual.
