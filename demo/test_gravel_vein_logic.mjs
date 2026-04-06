/**
 * Regression tests for gravel "g" vein thickness logic (mirrors index.html).
 * Run: node demo/test_gravel_vein_logic.mjs
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function lithoParseDepthFt(v) {
  if (v == null || v === '') return NaN;
  return parseFloat(String(v).replace(/,/g, '').replace(/[^\d.\-]/g, ''));
}

function lithoFormationName(layer) {
  if (!layer || typeof layer !== 'object') return '';
  return String(
    layer.formation || layer.Formation || layer.FORMATION || layer.material || layer.Material ||
      layer.lithology || layer.Lithology || layer.LITHOLOGY || layer.description || layer.Description ||
      layer.strata || layer.Strata || layer.formationname || layer.FormationName ||
      layer.zone || layer.Zone || layer.desc || layer.Desc || layer.remarks || layer.Remarks ||
      layer.MATERIAL || ''
  ).trim();
}

function lithoLayerTopBottomFt(L, prevBot) {
  if (!L || typeof L !== 'object') return { top: NaN, bot: NaN };
  const top = lithoParseDepthFt(
    L.top ?? L.Top ?? L.from ?? L.From ?? L.from_ft ?? L.top_ft ?? L.fromdepth ??
      L.FromDepth ?? L.FROM_DEPTH ?? L.depth_top ?? L.DepthTop ?? L.start_depth ??
      L.StartDepth ?? L.start ?? L.Start ?? L.begin ?? NaN
  );
  const bot = lithoParseDepthFt(
    L.bottom ?? L.Bottom ?? L.to ?? L.To ?? L.to_ft ?? L.bottom_ft ?? L.todepth ??
      L.ToDepth ?? L.TO_DEPTH ?? L.depth_bottom ?? L.DepthBottom ?? L.end_depth ??
      L.EndDepth ?? L.end ?? L.End ?? L.stop ?? NaN
  );
  if (Number.isNaN(bot)) return { top, bot: NaN };
  let t = top;
  if (Number.isNaN(t)) t = Number.isNaN(prevBot) ? 0 : prevBot;
  return { top: t, bot };
}

function isNonproductiveLithologyRow(low) {
  if (!low || !String(low).trim()) return true;
  if (/dry\s*hole|no\s*water|abandon|plugged|cement\s*fill/i.test(low)) return true;
  return /\b(cement|grout|surface\s*seal|bentonite\s*seal|drive\s*shoe|empty\s*hole|void|fill|seal\s*only)\b/i.test(low) &&
    !/grav|gravel|sand/i.test(low);
}

function formationHasGravelVein(fmRaw) {
  const fm = String(fmRaw == null ? '' : fmRaw);
  const l = fm.toLowerCase();
  if (!l.trim()) return false;
  if (/dry\s*hole|no\s*water|abandon|plugged/i.test(l)) return false;
  if (/\bsandstone\b|\bsiltstone\b/i.test(l) && !/grav/i.test(l)) return false;
  if (/\b(shale|limestone|dolomite|bedrock)\b/i.test(l) && !/sand|grav|gravel|drift|outwash/i.test(l)) return false;
  if (/grav|gravel|pea\s*grav|gravelly|w\s*\/\s*grav|water\s*grav|water\s*gravel|w\.?\s*grav/i.test(l)) return true;
  if (/g\s*&\s*g|s\s*&\s*g|s\.\s*g\.|s\/g\b/i.test(l)) return true;
  if (/sand\s*(\(|&|and|\/|,)\s*gravel|gravel\s*(\(|&|and|\/|,)\s*sand/i.test(l)) return true;
  if (/\bgr\b/.test(l) && !/grout|program|agree|energy|degree|dig/i.test(l)) return true;
  return false;
}

function sortLithLayersByDepth(layers) {
  return layers.slice().sort((a, b) => {
    const tba = lithoLayerTopBottomFt(a, NaN);
    const tbb = lithoLayerTopBottomFt(b, NaN);
    let ta = tba.top; let tb = tbb.top;
    if (Number.isNaN(ta) && !Number.isNaN(tba.bot)) ta = tba.bot;
    if (Number.isNaN(tb) && !Number.isNaN(tbb.bot)) tb = tbb.bot;
    if (Number.isNaN(ta) && Number.isNaN(tb)) return 0;
    if (Number.isNaN(ta)) return 1;
    if (Number.isNaN(tb)) return -1;
    if (ta !== tb) return ta - tb;
    const ba = Number.isNaN(tba.bot) ? ta : tba.bot;
    const bb = Number.isNaN(tbb.bot) ? tb : tbb.bot;
    return ba - bb;
  });
}

function gravelVeinThicknessFtFromLithology(layers) {
  if (!layers || !layers.length) return null;
  const sorted = sortLithLayersByDepth(layers);
  let prevBot = NaN;
  let bestThick = null;
  let runTop = NaN;
  let runBot = NaN;
  function flushRun() {
    if (!Number.isNaN(runTop) && !Number.isNaN(runBot) && runBot > runTop) {
      const th = runBot - runTop;
      if (bestThick == null || th > bestThick) bestThick = th;
    }
    runTop = NaN;
    runBot = NaN;
  }
  for (const L of sorted) {
    const fm = lithoFormationName(L);
    const low = fm.toLowerCase();
    const tb = lithoLayerTopBottomFt(L, prevBot);
    if (!Number.isNaN(tb.bot)) prevBot = tb.bot;
    if (isNonproductiveLithologyRow(low)) {
      flushRun();
      continue;
    }
    if (!formationHasGravelVein(fm)) {
      flushRun();
      continue;
    }
    const { top, bot } = tb;
    if (Number.isNaN(bot) || bot <= top) {
      flushRun();
      continue;
    }
    if (Number.isNaN(runTop)) {
      runTop = top;
      runBot = bot;
    } else if (top <= runBot + 0.05) {
      if (bot > runBot) runBot = bot;
    } else {
      flushRun();
      runTop = top;
      runBot = bot;
    }
  }
  flushRun();
  if (bestThick != null) return Math.round(bestThick);
  prevBot = NaN;
  for (const L2 of sorted) {
    const fm2 = lithoFormationName(L2);
    const low2 = fm2.toLowerCase();
    const tb2 = lithoLayerTopBottomFt(L2, prevBot);
    if (!Number.isNaN(tb2.bot)) prevBot = tb2.bot;
    if (isNonproductiveLithologyRow(low2) || !formationHasGravelVein(fm2)) continue;
    if (Number.isNaN(tb2.bot) || tb2.bot <= tb2.top) continue;
    const th = tb2.bot - tb2.top;
    if (bestThick == null || th > bestThick) bestThick = th;
  }
  return bestThick != null ? Math.round(bestThick) : null;
}

function assertEq(name, got, exp) {
  if (got !== exp) {
    console.error(`FAIL ${name}: expected ${exp}, got ${got}`);
    process.exit(1);
  }
  console.log(`ok ${name}: ${got}`);
}

// --- Expected g values (see demo/gravel_vein_demo_wells.csv) ---
assertEq('sand-only well (no gravel) → no g', gravelVeinThicknessFtFromLithology(JSON.parse('[{"top":0,"bottom":12,"formation":"CEMENT GROUT"},{"top":12,"bottom":95,"formation":"SAND"}]')), null);
assertEq('SA & GR single interval', gravelVeinThicknessFtFromLithology(JSON.parse('[{"top":0,"bottom":10,"formation":"CEMENT"},{"top":10,"bottom":35,"formation":"SA & GR"},{"top":35,"bottom":120,"formation":"SHALE"}]')), 25);
assertEq('merged PEA GRAV + GRAVEL', gravelVeinThicknessFtFromLithology(JSON.parse('[{"top":0,"bottom":20,"formation":"CLAY"},{"top":20,"bottom":28,"formation":"PEA GRAV"},{"top":28,"bottom":40,"formation":"GRAVEL"},{"top":40,"bottom":100,"formation":"LIMESTONE"}]')), 20);
assertEq('wrapped intervals + from_ft', gravelVeinThicknessFtFromLithology(JSON.parse('[{"from_ft":5,"to_ft":30,"material":"SAND & GRAVEL"},{"from_ft":30,"to_ft":88,"material":"DOLOMITE"}]')), 25);
assertEq('out-of-order rows sort correctly', gravelVeinThicknessFtFromLithology(JSON.parse('[{"top":60,"bottom":80,"formation":"GRAVEL"},{"top":40,"bottom":60,"formation":"SAND"},{"top":80,"bottom":90,"formation":"SHALE"}]')), 20);
assertEq('FromDepth aliases', gravelVeinThicknessFtFromLithology(JSON.parse('[{"FromDepth":15,"ToDepth":42,"Lithology":"WATER GRAV"},{"FromDepth":42,"ToDepth":75,"Lithology":"LIMESTONE"}]')), 27);

// Smoke: demo CSV last column is RFC-4180 quoted JSON
const csvPath = path.join(__dirname, 'gravel_vein_demo_wells.csv');
const text = fs.readFileSync(csvPath, 'utf8');
const lines = text.split(/\r?\n/).filter(Boolean);
for (let li = 1; li < lines.length; li++) {
  const line = lines[li];
  const id = line.split(',')[0];
  const m = line.match(/,(?:\d*|),"(.*)"\s*$/);
  if (!m) {
    console.error('Could not extract lithology_json from line:', line.slice(0, 80));
    process.exit(1);
  }
  const jsonStr = m[1].replace(/""/g, '"');
  let layers;
  try {
    const parsed = JSON.parse(jsonStr);
    layers = parsed.intervals || parsed;
  } catch (e) {
    console.error('JSON parse fail', id, e.message);
    process.exit(1);
  }
  const gExplicitMatch = line.match(/Field Located,([^,]*),"/);
  const gRaw = gExplicitMatch ? gExplicitMatch[1].trim() : '';
  const gExplicit = gRaw === '' ? null : Math.round(parseFloat(gRaw, 10));
  const gCalc = gravelVeinThicknessFtFromLithology(layers);
  if (gExplicit != null && !Number.isNaN(gExplicit) && gCalc != null && gExplicit !== gCalc) {
    console.error(`Mismatch ${id}: g_vein_ft column=${gExplicit} litho-derived=${gCalc} (fix demo or pipeline)`);
    process.exit(1);
  }
  console.log(`csv row ${id}: litho g=${gCalc ?? 'null'}${gExplicit != null ? ` (column ${gExplicit} matches)` : ''}`);
}

console.log('\nAll gravel vein tests passed.');
