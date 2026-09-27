# Well viewer (static, hub-local)

Everything under this directory that the page loads at runtime lives **in this repository**:

- `index.html`, `manifest.json`, `icon.png`
- `vendor/` — Leaflet, MarkerCluster, PapaParse (vendored files; **not** loaded from other projects or CDNs after sync)
- `api/dnr-report.js` — duplicate of the viewer’s DNR report script (same bytes also power `apps/hub/vendor/dnr-report-local/index.cjs` for Next `/api/dnr-report`)
- `dnr_wells_chunk_*.csv.gz` and `litho_parts/` when present (often large; may be gitignored in some clones)

Re-sync from your standalone viewer checkout (one-way **copy** into the hub; no symlinks, no runtime path into that repo):

```bash
export WELL_VIEWER_ROOT="/absolute/path/to/your/viewer-clone"
./scripts/sync-well-viewer-into-hub.sh
```

The script requires the viewer folder to include `leaflet.js`, `leaflet.css`, `markercluster*.js/css`, and `api/dnr-report.js` so those files are **duplicated** into `vendor/` and `api/` here. PapaParse is fetched from cdnjs once during sync into `vendor/papaparse.min.js`.

After syncing, commit changed assets so deploys stay self-contained.
