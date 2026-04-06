#!/usr/bin/env node
/**
 * Validates lithology aggregate helpers (sum-all sand/gravel/water-bearing intervals, list, CSV keyword scan).
 * Mirrors index.html — update both when changing those functions.
 *
 * Run: node tests/run_litho_aggregate_tests.cjs
 */

'use strict';

var _lithoCache = {};

function lithologyLooksLikeIntervals(arr) {
  if (!arr || !arr.length || typeof arr[0] !== 'object') return false;
  var z = arr[0];
  return (
    z.top != null ||
    z.bottom != null ||
    z.Top != null ||
    z.Bottom != null ||
    z.from != null ||
    z.to != null ||
    z.From != null ||
    z.To != null ||
    z.depth_top != null ||
    z.depth_bottom != null ||
    z.DepthTop != null ||
    z.DepthBottom != null ||
    z.start_depth != null ||
    z.end_depth != null ||
    z.formation != null ||
    z.Formation != null ||
    z.material != null ||
    z.Material != null
  );
}

function tryParseLithologyArray(raw) {
  if (raw == null || raw === '') return null;
  if (Array.isArray(raw)) return lithologyLooksLikeIntervals(raw) ? raw : null;
  if (typeof raw === 'object' && raw !== null) {
    if (lithologyLooksLikeIntervals([raw])) return [raw];
    return null;
  }
  var s = String(raw).trim().replace(/^\ufeff/, '');
  if (!s) return null;
  if (s.charAt(0) === '"') {
    try {
      var unq = JSON.parse(s);
      if (typeof unq === 'string') s = unq.trim().replace(/^\ufeff/, '');
    } catch (e0) {}
  }
  if (s.charAt(0) !== '[') {
    var i0 = s.indexOf('[');
    var i1 = s.lastIndexOf(']');
    if (i0 >= 0 && i1 > i0) s = s.slice(i0, i1 + 1);
  }
  if (s.charAt(0) !== '[') return null;
  try {
    var j = JSON.parse(s);
    if (typeof j === 'string') j = JSON.parse(String(j).trim().replace(/^\ufeff/, ''));
    if (j && j.length && lithologyLooksLikeIntervals(j)) return j;
  } catch (e) {}
  return null;
}

function getLithLayers(w) {
  var key = w.id || '';
  if (_lithoCache[key] !== undefined) return _lithoCache[key];
  var layers = null;
  var tryList = [
    w.lithology_json,
    w.lithology,
    w.lithologyjson,
    w.strata_json,
    w.log_json,
    w.well_log_json,
    w.materials_json,
  ];
  for (var ti = 0; ti < tryList.length; ti++) {
    layers = tryParseLithologyArray(tryList[ti]);
    if (layers) break;
  }
  if (!layers && w && typeof w === 'object') {
    var keys = Object.keys(w);
    keys.sort(function (a, b) {
      var al = String(a).toLowerCase(),
        bl = String(b).toLowerCase();
      var ap = /lithology|strata|well_log|log_json|interval|formation|materials/.test(al) ? 0 : 1;
      var bp = /lithology|strata|well_log|log_json|interval|formation|materials/.test(bl) ? 0 : 1;
      if (ap !== bp) return ap - bp;
      return al.localeCompare(bl);
    });
    for (var ki = 0; ki < keys.length; ki++) {
      var pk = keys[ki];
      var kl = String(pk).toLowerCase();
      if (kl === 'id' || kl === 'lat' || kl === 'lon' || kl === 'report' || kl === 'refno' || kl.indexOf('url') >= 0)
        continue;
      layers = tryParseLithologyArray(w[pk]);
      if (layers) break;
    }
  }
  _lithoCache[key] = layers;
  return layers;
}

function lithoFormationName(layer) {
  if (!layer || typeof layer !== 'object') return '';
  return String(
    layer.formation ||
      layer.Formation ||
      layer.material ||
      layer.Material ||
      layer.lithology ||
      layer.Lithology ||
      layer.description ||
      layer.strata ||
      ''
  ).trim();
}

function lithoParseDepthFt(v) {
  if (v == null || v === '') return NaN;
  return parseFloat(String(v).replace(/,/g, '').replace(/[^\d.\-]/g, ''));
}

function lithoLayerTopBottomFt(L, prevBot) {
  if (!L || typeof L !== 'object') return { top: NaN, bot: NaN };
  var top = lithoParseDepthFt(
    L.top != null
      ? L.top
      : L.Top != null
        ? L.Top
        : L.from != null
          ? L.from
          : L.From != null
            ? L.From
            : L.depth_top != null
              ? L.depth_top
              : L.DepthTop != null
                ? L.DepthTop
                : L.start_depth != null
                  ? L.start_depth
                  : L.StartDepth
  );
  var bot = lithoParseDepthFt(
    L.bottom != null
      ? L.bottom
      : L.Bottom != null
        ? L.Bottom
        : L.to != null
          ? L.to
          : L.To != null
            ? L.To
            : L.depth_bottom != null
              ? L.depth_bottom
              : L.DepthBottom != null
                ? L.DepthBottom
                : L.end_depth != null
                  ? L.end_depth
                  : L.EndDepth
  );
  if (isNaN(bot)) return { top: top, bot: NaN };
  if (isNaN(top)) {
    if (!isNaN(prevBot)) top = prevBot;
    else top = 0;
  }
  return { top: top, bot: bot };
}

/** Minimal depth for tests (full viewer also uses litho max bottom / casing). */
function getWellDisplayDepthFt(w) {
  if (!w || typeof w !== 'object') return null;
  var d = w.depth != null && w.depth !== '' ? parseFloat(String(w.depth).replace(/,/g, '')) : NaN;
  if (!isNaN(d) && d > 0) return Math.round(d);
  return null;
}

var _rockFormations = /lime|dolomite|shale|slate|sandstone|siltstone|bedrock|granite|marble|rock/i;

function isWaterBearingFormation(fmRaw) {
  var l = String(fmRaw == null ? '' : fmRaw).toLowerCase();
  if (!l.trim()) return false;
  if (/dry\s*hole|no\s*water|abandon|plugged|cement\s*fill/i.test(l)) return false;
  if (
    (/limestone|dolomite|shale|slate|bedrock|granite|marble|\b(ls|lm|dl)\b/i.test(l)) &&
    !/sand|grav|gravel|drift|sa\b|gr\b|sg\b|outwash|till/i.test(l)
  )
    return false;
  if (
    (/\bsandstone\b|\bsiltstone\b/i.test(l)) &&
    !/grav|gravel|drift|glacial|outwash|till/i.test(l)
  )
    return false;
  if (
    /grav|gravel|\bsg\b|sand\s*\/\s*g|s\s*&\s*g|sand\s*grav|water\s*b\.?|water\s*bearing|water\s*grav|pea\s*grav|gravelly|w\s*\/\s*grav|producing|\baquifer\b|unconsolidated|water\s*zone|pervious|glacial\s*drift/i.test(
      l
    )
  )
    return true;
  if (l.indexOf('sandstone') >= 0 || l.indexOf('siltstone') >= 0) return false;
  if (/\bwet\b/.test(l) && /sand|grav|gravel|sa\b|gr\b|silt|drift/i.test(l)) return true;
  if (/\b(sa|gr|sg)\b/.test(l)) return true;
  if (/\bsand\b/.test(l) && /\bclayey\s*sand\b|sandy\s*clay|sand\s*(and|&|\/)\s*clay|clay\s*(and|&|\/)\s*sand/i.test(l))
    return true;
  if (/\bsand\b/.test(l) && l.indexOf('clay') < 0) return true;
  if (l.indexOf('sand') >= 0 && (l.indexOf('gravel') >= 0 || l.indexOf('water') >= 0 || l.indexOf('bearing') >= 0))
    return true;
  return false;
}

function lithoLooksLikeSandGravelMaterial(fmRaw) {
  var l = String(fmRaw == null ? '' : fmRaw).toLowerCase();
  if (!l.trim()) return false;
  if (/dry\s*hole|no\s*water|abandon|plugged/i.test(l)) return false;
  if (
    (/shale|limestone|dolomite|slate|bedrock|granite|marble/i.test(l) || /\b(ls|lm|dl)\b/i.test(l)) &&
    !/sand|grav|sa\b|gr\b|drift/i.test(l)
  )
    return false;
  return /grav|gravel|\bsand\b|\bsa\b|\bgr\b|\bsg\b|s\s*\/\s*g|s\s*&\s*g|drift|outwash|glacial|fill|till/i.test(l);
}

function _testRockOnlyInterval(l) {
  return _rockFormations.test(l) && l.indexOf('sand and') === -1 && l.indexOf('gravel') === -1;
}

function sumAllSandGravelWaterBearingIntervalsFt(w) {
  var layers = getLithLayers(w);
  if (!layers || !layers.length) return null;
  var depthCap = getWellDisplayDepthFt(w);
  var maxD = depthCap != null && !isNaN(depthCap) && depthCap > 0 ? depthCap : Infinity;
  var prevBot = NaN;
  var sum = 0;
  for (var i = 0; i < layers.length; i++) {
    var L = layers[i];
    var fm = lithoFormationName(L);
    var l = fm.toLowerCase();
    if (!l.trim() || /no digitized|dnr report|placeholder/i.test(l)) continue;
    if (/dry\s*hole|no\s*water|abandon|plugged|cement\s*fill/i.test(l)) continue;
    var tb = lithoLayerTopBottomFt(L, prevBot);
    if (!isNaN(tb.bot)) prevBot = tb.bot;
    if (isNaN(tb.bot)) continue;
    var top = tb.top;
    if (isNaN(top)) continue;
    top = Math.max(0, top);
    var bot = Math.min(tb.bot, maxD);
    if (bot <= top) continue;
    if (_testRockOnlyInterval(l)) continue;
    if (!isWaterBearingFormation(fm) && !lithoLooksLikeSandGravelMaterial(fm)) continue;
    sum += bot - top;
  }
  if (sum <= 0) return null;
  return Math.round(sum);
}

function cjListSandGravelAquiferLayers(w) {
  var layers = getLithLayers(w);
  if (!layers || !layers.length) return [];
  var depthCap = getWellDisplayDepthFt(w);
  var maxD = depthCap != null && !isNaN(depthCap) && depthCap > 0 ? depthCap : Infinity;
  var prevBot = NaN;
  var out = [];
  for (var i = 0; i < layers.length; i++) {
    var L = layers[i];
    var fm = lithoFormationName(L);
    var l = fm.toLowerCase();
    if (!l.trim() || /no digitized|dnr report|placeholder/i.test(l)) continue;
    if (/dry\s*hole|no\s*water|abandon|plugged|cement\s*fill/i.test(l)) continue;
    var tb = lithoLayerTopBottomFt(L, prevBot);
    if (!isNaN(tb.bot)) prevBot = tb.bot;
    if (isNaN(tb.bot) || isNaN(tb.top)) continue;
    var top = Math.max(0, tb.top);
    var bot = Math.min(tb.bot, maxD);
    if (bot <= top) continue;
    if (_testRockOnlyInterval(l)) continue;
    if (!isWaterBearingFormation(fm) && !lithoLooksLikeSandGravelMaterial(fm)) continue;
    out.push({ formation: fm, top: top, bottom: bot, thickFt: Math.round(bot - top) });
  }
  return out;
}

var _cjCsvSkipKeyForKeywordScan = /^(lat|lon|id|utm_|png|jpg|jpeg|gif|webp|pdf|sha|hash|etag)$/i;
var _cjSandGravelKeywordHint =
  /grav|gravel|sand\s*(and|&|\/)\s*grav|sand\s*grav|pea\s*grav|\bsg\b|\bsa\b\s*[&,/]\s*\bgr\b|water\s*bear|unconsolidated|glacial\s*drift|outwash|aquifer|drift(?!\s*less)|\b(sa|gr)\b(?!\w)/i;

function cjScanRowStringsForSandGravelKeywords(w) {
  if (!w || typeof w !== 'object') return [];
  var hits = [];
  var keys = Object.keys(w);
  for (var ki = 0; ki < keys.length; ki++) {
    var k = keys[ki];
    var kl = String(k).toLowerCase();
    if (_cjCsvSkipKeyForKeywordScan.test(k) && kl.indexOf('lithology') < 0 && kl.indexOf('formation') < 0)
      continue;
    var v = w[k];
    if (v == null) continue;
    var s = '';
    if (typeof v === 'string') s = v;
    else if (typeof v === 'number') continue;
    else if (typeof v === 'object') {
      try {
        s = JSON.stringify(v);
      } catch (e) {
        continue;
      }
      if (s.length > 800) s = s.slice(0, 800);
    }
    s = String(s).trim();
    if (s.length < 4) continue;
    if (!_cjSandGravelKeywordHint.test(s)) continue;
    hits.push({ field: k, snippet: s.length > 140 ? s.slice(0, 137) + '…' : s });
  }
  return hits;
}

function assertEq(got, want, name) {
  if (got !== want) {
    throw new Error(name + ': expected ' + want + ', got ' + got);
  }
}

function uid() {
  return 'node-' + Math.random().toString(36).slice(2, 11);
}

var passed = 0;
function ok(label) {
  passed++;
  console.log('ok:', label);
}

try {
  var w1 = {
    id: uid(),
    depth: '100',
    lithology_json: JSON.stringify([
      { top: 0, bottom: 10, formation: 'clay' },
      { top: 10, bottom: 25, formation: 'sand and gravel' },
      { top: 25, bottom: 40, formation: 'LIMESTONE' },
      { top: 40, bottom: 55, formation: 'SA & GR water bearing' },
    ]),
  };
  assertEq(sumAllSandGravelWaterBearingIntervalsFt(w1), 30, 'sum_multi');
  assertEq(cjListSandGravelAquiferLayers(w1).length, 2, 'list_len');
  ok('sum_multi_intervals_30ft + two listed layers');

  var w2 = {
    id: uid(),
    depth: '50',
    lithology_json: JSON.stringify([{ top: 0, bottom: 80, formation: 'coarse sand' }]),
  };
  assertEq(sumAllSandGravelWaterBearingIntervalsFt(w2), 50, 'depth_clip');
  ok('depth_clip_to_completed');

  var w3 = {
    id: uid(),
    depth: '40',
    lithology_json: JSON.stringify([{ top: 0, bottom: 40, formation: 'No digitized table for this well' }]),
  };
  assertEq(sumAllSandGravelWaterBearingIntervalsFt(w3), null, 'placeholder');
  ok('skip_placeholder_formation');

  var w4 = {
    id: uid(),
    depth: '20',
    aquifer: 'Unconsolidated sand and gravel aquifer',
    county: 'Test',
  };
  var hits = cjScanRowStringsForSandGravelKeywords(w4);
  if (!hits.some(function (h) {
    return h.field === 'aquifer';
  }))
    throw new Error('keyword_scan: missing aquifer hit');
  ok('csv_keyword_aquifer');

  var w5 = {
    id: uid(),
    depth: '100',
    lithology_json: JSON.stringify([
      { top: 5, bottom: 20, formation: 'gravel' },
      { top: 25, bottom: 35, formation: 'pea gravel' },
    ]),
  };
  assertEq(sumAllSandGravelWaterBearingIntervalsFt(w5), 25, 'two_gravel_zones');
  ok('gravel_plus_pea_gravel_25ft');

  console.log('');
  console.log('All', passed, 'lithology aggregate unit tests passed.');
  process.exit(0);
} catch (e) {
  console.error('FAIL:', e.message);
  process.exit(1);
}
