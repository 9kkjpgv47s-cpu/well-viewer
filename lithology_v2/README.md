# Lithology V2 (isolated classification layer)

This folder is **fully separate** from original lithology sources:

- Does **not** edit `lithology_json` in chunks
- Does **not** change `dnr_wells_chunk_*.csv.gz`, `dnr_html_litho_cache.json`, or WellLogs CSVs
- All v2 artifacts live under `lithology_v2/` plus an optional runtime sidecar fetch path

## Rollback

1. **Viewer / hub:** Turn off v2 — remove `?litho_v2=1` or set `USE_LITHOLOGY_V2 = false`. No data rebuild required.
2. **Delete v2 entirely:** Remove the `lithology_v2/` directory and `well_classification_v2.jsonl.gz` copy if deployed.
3. **Original pipeline unchanged:** `build_statewide_data.py` and v1 regex in `index.html` continue to work as before.

## Pipeline

```bash
# 1) Mine every formation string + word frequencies (read-only scan of chunks)
python3 lithology_v2/mine_formation_vocabulary.py

# 2) Build categorized lexicon from mine + geologic rules
python3 lithology_v2/build_lexicon_from_mine.py

# 3) Build per-well sidecar overlay
python3 lithology_v2/build_v2_sidecar.py

# 4) Optional: verify vs v1
python3 lithology_v2/verify_v2.py
```

## Outputs

| File | Purpose |
|------|---------|
| `docs/formation_vocabulary_full.csv` | Every distinct formation text + layer counts |
| `docs/formation_word_frequency.csv` | Token frequency across all logs |
| `docs/bedrock_aquifer_v1_gravel_wells.csv` | Wells where registry says bedrock but v1 lithology says gravel |
| `formation_lexicon.json` | Pattern + exact term → category (rock / unconsolidated / mixed / overburden) |
| `out/well_classification_v2.jsonl.gz` | Per-refno `well_type_v2`, `label_kind_v2`, thicknesses |

## Viewer / hub usage

- Script: `lithology-v2-loader.js`
- Sidecar URL: `lithology_v2/out/well_classification_v2.jsonl.gz`
- Enable: `?litho_v2=1` on the well viewer URL

## Key fixes in v2

- **Sandrock** (+ water/producing variants) → bedrock, not sand/gravel
- **LIME / LS / SS** abbreviations → bedrock
- **TOP SOIL / FILL** → overburden (does not alone make a bedrock well “gravel”)
- Bedrock aquifer + rock top + thin surface S&G → stays **rock**

## Editing rules

1. Adjust patterns in `build_lexicon_from_mine.py` → re-run steps 2–3.
2. Tune well policy in `formation_lexicon.json` → `well_type_policy`.
3. Never edit original lithology files; only regenerate sidecar.
