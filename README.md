# C&J Well Viewer (DNR)

Static Indiana DNR map (`index.html`) and Python ETL that produces `dnr_wells_chunk_*.csv.gz`. **Vercel:** commit **`dnr_wells_chunk_*.csv.gz` in the repo root** next to `index.html` (same pattern as `statewide_wells_chunk_*.csv.gz`). A dedicated `dnr-chunks/` folder returned **404** on production while root-level `.csv.gz` files were served. Do **not** use a root **`public/`** folder for chunks only: with the “Other” preset, Vercel treats `public/` as the *only* static output directory, so root `index.html` would not deploy.

## Keeping this repo separate from Drill Hub

These are **two products**. This repo must stay a **standalone** viewer (map, wells, DNR report API). The **Drill Hub** (Next.js, scheduler, driller job list) belongs in **its own** git repo and directory.

- **Wrong:** Pasting hub UI and scripts (`cj-hub-*`, `CJ_DRILLER_JOB_KEY`, scheduler/driller tabs) into root **`index.html`** here, or committing the whole hub app inside this folder.
- **Right:** Develop the hub elsewhere; use the hub’s **sync script** to copy **this** repo’s built static files into the hub’s `public/well-viewer/` (viewer → hub only).
- **Guardrails:** See `.cursor/rules/well-viewer-boundaries.mdc` (for Cursor) and `.gitignore` (ignores common hub folder names if they appear locally).

If `index.html` mentions “Drill Hub” or `cj-hub-bar`, the trees have crossed again — remove hub-only sections or reset that file from a clean standalone commit before shipping.

**Check:** `./scripts/verify-viewer-not-merged-with-hub.sh` — exits with an error if hub-only strings appear in root `index.html` (run before commit; wire into CI when ready).

- **Run locally:** open **`index.html`** or `python3 -m http.server 8080` in this folder.
- **Deploy to Vercel:** project root = this folder. Chunk files must be **`dnr_wells_chunk_*.csv.gz` at repo root** (or override `window.CJ_CHUNK_BASE_URL`). Run:
  - `npx vercel` (preview) or `npx vercel --prod` (production)
  - When linking, use a **dedicated** project for this app (see `DEPLOY_VERCEL.txt`).
- **Regenerate `index.html`:** `python3 finalize_viewer_index.py` (optional).
- **Rebuild data:** `python3 build_statewide_data.py` then `python3 merge_datajs_veins_into_index.py` — commit/deploy the new `.csv.gz` files with `index.html`.
- **Wells without CSV lithology:** `python3 list_wells_missing_lithology.py --summary-only` (counts empty `lithology_json` in chunks). On **Vercel**, opening a well calls **`/api/dnr-report`** to parse the same **HTML table** as the DNR details page (no OCR). Pure image/PDF scans show an embed + link; interval OCR is not implemented — use WellLogs CSV for that.
- **Light static bundle (9 counties):** Edit **`nine_counties.txt`**, then **`./build_nine_counties.sh`** (or `DNR_COUNTIES_FILE=nine_counties.txt python3 build_statewide_data.py`). Chunks contain only those counties — **smaller download** in poor-coverage areas. Lithology + vein columns are **pre-merged from WellLogs** at build time (same reliability idea as g labels: figure it out before deploy). **`index.html`** sets **`CJ_STATIC_DEPLOY = true`** so the map **does not** call `/api/dnr-report` or `litho_parts/` — only chunk fetches + map CDNs. Set **`CJ_STATIC_DEPLOY = false`** if you want the API fallback while you fill WellLogs gaps. Verify coverage: **`python3 verify_county_lithology_coverage.py`**.
- **Why not mega hardcode in HTML:** Putting tens of thousands of wells in `index.html` would be huge and slow on low-end phones; **gzip chunks** are the same “everything decided upfront” idea with a payload that scales.
