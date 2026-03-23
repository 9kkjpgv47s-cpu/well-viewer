# Getting Started: Full DNR Dataset (147k+ Wells)

The C&J Well Viewer loads the **full Indiana DNR water well dataset** on every page open. Here’s how to get the data and make it load consistently.

---

## Step 1: Fetch the full dataset with the included script

The DNR search site has no download button. Indiana DNR serves the same data via an **ArcGIS REST API**. Use the included script (no scraping).

### Run the script

1. In Terminal:  
   `cd "/Users/dominiceasterling/DNR_Well_Viewer_Full_Demo"`
2. Run: `python3 fetch_dnr_wells.py` — writes **dnr_wells_full.csv**. To test: `python3 fetch_dnr_wells.py --limit 2000` first, then run without --limit for full set. If you get 403, try a different network.

3. (Optional) Run a search that returns **all wells** (or the largest set you need):
   - Use the broadest filters (e.g. all counties, no date limit), or
   - If there is an “export all” or “download full dataset” option, use that.

3. Download the result. You typically get:
   - **wells.txt** — tab-delimited, one row per well, with `refno` and coordinate columns.
   - **litho.txt** — lithology; not needed for the map.

4. If the export is **county-by-county or in chunks**, repeat for each area and combine the `wells.txt` files (one header row, then all data rows).

### Option B — Request the full dataset from DNR

If the web search doesn’t offer a single “full state” export:

1. Contact **Indiana DNR Division of Water** (or the unit that maintains the well database).
2. Ask for a **full export of water well records** in tab-delimited or CSV format, with:
   - Well reference number (`refno`)
   - Coordinates (latitude/longitude preferred; UTM Zone 16 is also OK)
   - Any other fields you want (county, depth, aquifer, owner, etc.).

3. Save the file they provide (or convert it) as described in Step 2.

---

## Step 2: Use the CSV the script created

The script writes **dnr_wells_full.csv** in the project folder (same folder as `index.html`). No need to move or rename it. If you ever get data from DNR another way (e.g. `wells.txt`), save or rename it to **dnr_wells_full.csv** in that same folder.

---

## Step 3: Make sure the format is compatible

The app needs:

- **First row:** Headers (column names).
- **One row per well.**

It looks for these columns (any casing; extra columns are kept):

| Purpose    | Column names the app recognizes |
|-----------|----------------------------------|
| Well ID   | `refno`, `ref_no`, `id`, `permit` |
| Latitude  | `lat`, `latitude`, `y` |
| Longitude | `lon`, `longitude`, `long`, `x` |
| **Or (UTM)** | `utm_x` / `easting` and `utm_y` / `northing` (Indiana = UTM Zone 16) |

If your file has **only UTM** (e.g. `utm_x`, `utm_y` or `easting`, `northing`), the app will convert them to lat/lon for the map.

- **Optional but useful:** `depth`, `county`, `aquifer`, `owner`, etc. — they show in the well list and detail view.

If the DNR gives you **wells.txt** (tab-delimited) with different header names, you can:

- Rename it to `dnr_wells_full.csv` and ensure the header row has at least refno + lat/lon **or** UTM columns, or  
- Rename the columns in the first row to match the table above (e.g. `latitude` / `longitude` or `utm_x` / `utm_y`), then save as `dnr_wells_full.csv`.

---

## Step 4: Test locally

1. Open a terminal in the project folder:
   ```bash
   cd "/Users/dominiceasterling/DNR_Well_Viewer_Full_Demo"
   python3 -m http.server 8080
   ```
2. In the browser go to: **http://localhost:8080**
3. You should see “Loading full DNR dataset…” then “Loaded 147,000 wells” (or your row count). The map should show clusters across Indiana.

If you see “Full CSV not found or failed. Using 65 built-in wells”:

- Confirm the file is named **`dnr_wells_full.csv`** and is in the same folder as **`index.html`**.
- Confirm the first row is headers and that you have at least refno + lat/lon **or** UTM columns.

---

## Step 5: Deploy to Vercel so it’s consistent

1. Make sure **`dnr_wells_full.csv`** is in the project and committed:
   ```bash
   cd "/Users/dominiceasterling/DNR_Well_Viewer_Full_Demo"
   git add dnr_wells_full.csv index.html
   git commit -m "Add full DNR dataset"
   git push
   ```
2. Deploy:
   ```bash
   npx vercel --prod
   ```
3. Open the Vercel URL. The app will load **`dnr_wells_full.csv`** from that URL every time (e.g. `https://your-project.vercel.app/dnr_wells_full.csv`).

**Note:** The CSV may be several MB. Vercel has a 50 MB limit per file; if you hit limits, we can switch to a chunked or compressed approach later.

---

## Step 6: Iterate for consistency

- **Wrong or missing columns:** Adjust the header row in your export or in a script so the app sees `refno`, `lat`/`lon` (or `utm_x`/`utm_y`).
- **Encoding:** Save the CSV as **UTF-8** if you have special characters.
- **Duplicates:** If you merged multiple exports, remove duplicate header rows (keep one header, then all data rows).
- **Performance:** 147k rows is fine; the app uses clustering. If you add more data later and things slow down, we can add paging or filtering.

Once the file is in place and the app loads it every time (locally and on Vercel), you’re set. From there we can tweak column mapping, UTM handling, or deployment if anything doesn’t match.

---

## Well Log (material by footage) & test rate / GPM (deployed app only)

The **ArcGIS CSV does not include** the DNR PDF’s **Well Log** table (Top / Bottom / Formation) or **Well Capacity Test** (test rate in gpm, bail rate). Those exist only on the official DNR report page.

After **Vercel deploy**, the app calls **`/api/dnr-report?refNo=…`** (see `api/dnr-report.js`). That serverless route fetches the DNR HTML report and parses:

- **Material drilled through** — Well Log rows (footage intervals + formation text), same as the red-circled area on the PDF.
- **Test rate / GPM / yield / bail** — same as the blue-circled “Test rate … gpm” (and bail line when present), plus static water level when parsed.

**Local `file://` open:** the API is not available; the summary falls back to CSV (depth to bedrock, casing, etc.). Use **`npx vercel dev`** or deploy to see full Well Log + test rate on tap.

**Custom API base (optional):** set `window.CJ_DNR_REPORT_API = 'https://your-app.vercel.app/api/dnr-report'` if the page is hosted elsewhere.

---

## Full Well Log (every Top / Bottom / Formation row)

The DNR report page often **does not send Well Log rows in the first HTML** (only the column headers until JavaScript runs), so **`/api/dnr-report` may not fill the table**. To get **every interval** exactly as in the official log:

1. From Indiana DNR, download the same export that includes **`litho.txt`** (Well Log) with **`wells.txt`** / well records.
2. Run:
   ```bash
   cd "/Users/dominiceasterling/DNR_Well_Viewer_Full_Demo"
   python3 merge_litho_into_wells.py /path/to/litho.txt dnr_wells_full.csv -o dnr_wells_full_with_litho.csv
   ```
   Replace `dnr_wells_full.csv` with your current wells file if needed.
3. Re-chunk and redeploy:
   ```bash
   python3 chunk_dnr_csv.py dnr_wells_full_with_litho.csv
   ```
   (Update `chunk_dnr_csv.py` INPUT or pass the new CSV path.)

The merged CSV gains a **`lithology_json`** column (array of `{top, bottom, formation}` per row). The app shows **all** of those rows under **Top / Bottom / Formation** — same as the paper/PDF Well Log. If column names in `litho.txt` don’t match, edit `merge_litho_into_wells.py` column detection or the header row in your file.
