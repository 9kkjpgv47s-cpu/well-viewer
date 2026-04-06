/**
 * Regression tests for gravel "g" and rock "r" lithology matching (mirrors index.html).
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

function normalizeFormationForLitho(s) {
  return String(s == null ? '' : s)
    .replace(/\u00a0/g, ' ')
    .replace(/[＆﹠]/g, '&')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

const _rockAbbrevToken = {
  hs: 1, as: 1, sh: 1, ss: 1, ls: 1, lm: 1, dl: 1, slt: 1, sst: 1, ch: 1, bd: 1, st: 1, mdl: 1, lst: 1,
  arg: 1, sil: 1, gn: 1, gnss: 1, bas: 1, dol: 1, lms: 1, shs: 1,
};

function formationHasGravelVein(fmRaw) {
  const l = normalizeFormationForLitho(fmRaw);
  if (!l) return false;
  if (/dry\s*hole|no\s*water|abandon|plugged/i.test(l)) return false;
  const sandGravelCombo = /grav|gravel|sand\s+and\s+gravel|gravel\s+and\s+sand|sand\s*,\s*gravel|gravel\s*,\s*sand|sand\s*(?:[&+/]|\()\s*gravel|gravel\s*(?:[&+/]|\()\s*sand/i;
  if (/\bsandstone\b|\bsiltstone\b/i.test(l) && !sandGravelCombo.test(l)) return false;
  if (/\b(shale|limestone|dolomite|bedrock)\b/i.test(l) && !/sand|grav|gravel|drift|outwash|glacial|esker|kame/i.test(l)) return false;
  if (/grav|gravel|pea\s*grav|gravelly|w\s*\/\s*grav|water\s*grav|water\s*gravel|w\.?\s*grav/i.test(l)) return true;
  if (/s\s*&\s*g\b|s\s*\+\s*g\b|s\s*\/\s*g\b|s\.\s*g\.|\bsng\b/i.test(l)) return true;
  if (sandGravelCombo.test(l)) return true;
  if (/\boutwash\b|\bglacial\s+drift\b|\besker\b|\bkame\b|\bterrace\s+(grav|gravel|sand)/i.test(l)) return true;
  if (/\bsa\s+gr\b|\bsi\s+sa\s+gr\b|\bw\s+gr\b/.test(l)) return true;
  if (/\bgr\b/.test(l) && !/grout|program|agree|energy|degree|dig/i.test(l)) return true;
  return false;
}

function formationIndicatesRockTop(fmRaw) {
  if (formationHasGravelVein(fmRaw)) return false;
  const fm = normalizeFormationForLitho(fmRaw);
  if (!fm) return false;
  if (/dry\s*hole|no\s*water|abandon|plugged/i.test(fm)) return false;
  if (/\b(lime\s*stone|limestone|dolomite|dolostone|shale|slate|mudstone|claystone|siltstone|sandstone|chert|granite|gneiss|basalt|bedrock|marble|coal)\b/.test(fm)) return true;
  if (/\brock\b/.test(fm) && !/sand|grav|gravel|drift|outwash/i.test(fm)) return true;
  if (/\b(soft|hard|stiff)\s+shale\b/.test(fm)) return true;
  if (/^(hs|as|sh|ss|ls|lm|dl|slt|sst|ch|bd|st|mdl)$/.test(fm)) return true;
  const parts = fm.split(/[,;/|]+/);
  for (const part of parts) {
    const seg = part.replace(/^[.\s]+|[.\s]+$/g, '').trim();
    if (!seg) continue;
    if (_rockAbbrevToken[seg]) return true;
  }
  const toks = fm.split(/\s+/);
  for (const rawTok of toks) {
    const t = rawTok.replace(/^[("]+|[)"']+$/g, '');
    if (_rockAbbrevToken[t]) return true;
  }
  return false;
}

function isNonproductiveLithologyRow(low) {
  if (!low || !String(low).trim()) return true;
  if (/dry\s*hole|no\s*water|abandon|plugged|cement\s*fill/i.test(low)) return true;
  return /\b(cement|grout|surface\s*seal|bentonite\s*seal|drive\s*shoe|empty\s*hole|void|fill|seal\s*only)\b/i.test(low) &&
    !/grav|gravel|sand/i.test(low);
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

function lithoDepthToRock(layers) {
  if (!layers) return null;
  let prevBot = NaN;
  for (const layer of layers) {
    const tb = lithoLayerTopBottomFt(layer, prevBot);
    if (!Number.isNaN(tb.bot)) prevBot = tb.bot;
    const fmRaw = lithoFormationName(layer);
    if (formationIndicatesRockTop(fmRaw)) {
      if (!Number.isNaN(tb.top) && tb.top >= 0) return Math.round(tb.top);
    }
  }
  return null;
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

function assertTrue(name, v) {
  if (!v) {
    console.error(`FAIL ${name}: expected true`);
    process.exit(1);
  }
  console.log(`ok ${name}`);
}

// --- Gravel phrase / abbreviation detection ---
assertTrue('S&G', formationHasGravelVein('S&G'));
assertTrue('S & G', formationHasGravelVein('S & G'));
assertTrue('S+G', formationHasGravelVein('S+G'));
assertTrue('S/G', formationHasGravelVein('S/G'));
assertTrue('S.G.', formationHasGravelVein('S.G.'));
assertTrue('SNG', formationHasGravelVein('SNG'));
assertTrue('sand and gravel', formationHasGravelVein('sand and gravel'));
assertTrue('sand, gravel', formationHasGravelVein('sand, gravel'));
assertTrue('outwash', formationHasGravelVein('OUTWASH'));

// --- Rock abbreviations (must NOT be treated as gravel) ---
assertTrue('HS is rock not gravel', !formationHasGravelVein('HS') && formationIndicatesRockTop('HS'));
assertTrue('AS is rock not gravel', !formationHasGravelVein('AS') && formationIndicatesRockTop('AS'));
assertTrue('hard shale phrase', formationIndicatesRockTop('HARD SHALE'));
assertTrue('soft shale phrase', formationIndicatesRockTop('SOFT SHALE'));

// --- SI SA GR is gravel aquifer code, not rock ---
assertTrue('SI SA GR is gravel', formationHasGravelVein('SI SA GR'));
assertTrue('SI SA GR not rock top', !formationIndicatesRockTop('SI SA GR'));

// --- Lithology stacks ---
assertEq('sand-only well → no g', gravelVeinThicknessFtFromLithology(JSON.parse('[{"top":0,"bottom":12,"formation":"CEMENT GROUT"},{"top":12,"bottom":95,"formation":"SAND"}]')), null);
assertEq('SA & GR single interval', gravelVeinThicknessFtFromLithology(JSON.parse('[{"top":0,"bottom":10,"formation":"CEMENT"},{"top":10,"bottom":35,"formation":"SA & GR"},{"top":35,"bottom":120,"formation":"SHALE"}]')), 25);
assertEq('merged PEA GRAV + GRAVEL', gravelVeinThicknessFtFromLithology(JSON.parse('[{"top":0,"bottom":20,"formation":"CLAY"},{"top":20,"bottom":28,"formation":"PEA GRAV"},{"top":28,"bottom":40,"formation":"GRAVEL"},{"top":40,"bottom":100,"formation":"LIMESTONE"}]')), 20);
assertEq('wrapped intervals + from_ft', gravelVeinThicknessFtFromLithology(JSON.parse('[{"from_ft":5,"to_ft":30,"material":"SAND & GRAVEL"},{"from_ft":30,"to_ft":88,"material":"DOLOMITE"}]')), 25);
assertEq('outwash thickness', gravelVeinThicknessFtFromLithology(JSON.parse('[{"top":0,"bottom":15,"formation":"CLAY"},{"top":15,"bottom":45,"formation":"GLACIAL OUTWASH"},{"top":45,"bottom":80,"formation":"SHALE"}]')), 30);
assertEq('S&G interval', gravelVeinThicknessFtFromLithology(JSON.parse('[{"top":0,"bottom":8,"formation":"CEMENT"},{"top":8,"bottom":33,"formation":"S&G"},{"top":33,"bottom":90,"formation":"HS"}]')), 25);

assertEq('r at HS abbreviation', lithoDepthToRock(JSON.parse('[{"top":0,"bottom":20,"formation":"SAND"},{"top":20,"bottom":100,"formation":"HS"}]')), 20);
assertEq('r at AS abbreviation', lithoDepthToRock(JSON.parse('[{"top":0,"bottom":40,"formation":"SA & GR"},{"top":40,"bottom":120,"formation":"AS"}]')), 40);
assertEq('r at SH,LM', lithoDepthToRock(JSON.parse('[{"top":0,"bottom":50,"formation":"SAND"},{"top":50,"bottom":100,"formation":"SH,LM"}]')), 50);

// Smoke: demo CSV
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
    console.error(`Mismatch ${id}: g_vein_ft column=${gExplicit} litho-derived=${gCalc}`);
    process.exit(1);
  }
  console.log(`csv row ${id}: litho g=${gCalc ?? 'null'}${gExplicit != null ? ` (column ${gExplicit} matches)` : ''}`);
}

console.log('\nAll gravel + rock lithology tests passed.');
