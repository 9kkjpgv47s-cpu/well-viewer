/**
 * DNR formation + construction classification v3 (browser / well-viewer).
 * Mirrors apps/hub/src/lib/formation-class.ts + dnr-well-classify.ts dual-label.
 *
 * Axes:
 *  - locationQuality: verified | estimated  (estimated → green marker)
 *  - formationClass: unconsolidated | rock | unknown
 *
 * Rock well construction:
 *  - no screen
 *  - casing at/into rock top (few ft into rock OK)
 *  - total depth > casing (open hole) — NEVER rock if no open hole below casing
 *
 * Revert: window.DNR_CLASSIFY_VERSION = 'v1' (or ?classify=v1)
 */
(function (global) {
  "use strict";

  var RULESET = "formation-class-v3-construction-2026-07-23-g-before-r";
  var MIN_UNCON_OVERRIDE_FT = 8;
  var CASING_ROCK_ABOVE_TOL_FT = 3;
  var CASING_INTO_ROCK_MAX_FT = 15;
  var MIN_OPEN_HOLE_ROCK_FT = 1.5;

  var DRY_RE = /dry\s*hole|no\s*water|abandon|plugged|cement\s*fill/i;
  var ROCK_AQ_RE =
    /\b(bedrock|limestone|dolomite|dolostone|shale|sandstone|siltstone|granite|marble)\b/i;
  var UNCON_AQ_RE = /\b(unconsolidated|sand|gravel|drift|outwash)\b/i;
  var SANDSTONE_FAMILY_RE =
    /sand\s*stone|sandstone|\bss\b|sand\s*[-_]?\s*rock|sandrock|sandy\s*rock|sandra\s*rock|sandr\s*rock|snd\s*rock|white\s*sand\s*rock|yel(?:low)?\s*sand\s*rock|brn\s*sand\s*rock|gray\s*sand\s*rock|grey\s*sand\s*rock|soft\s*sand\s*rock|hard\s*sand\s*rock/i;

  var PATTERN_RULES = [
    { id: "placeholder", re: /no digitized|merged welllogs|open dnr report|placeholder|^\s*-\s*$/i, cat: "ignore" },
    { id: "dry_abandon", re: DRY_RE, cat: "ignore" },
    { id: "sandstone_family", re: SANDSTONE_FAMILY_RE, cat: "rock" },
    { id: "hard_rock", re: /hard\s*rock|solid\s*rock|bedrock|rip\s*rap/i, cat: "rock" },
    { id: "limestone_dolomite", re: /limestone|dolomite|dolostone|lime\s*stone|\blime\b|gray\s*lime|grey\s*lime|br\s*lime|hard\s*lime|sandy\s*lime/i, cat: "rock" },
    { id: "shale_slate", re: /\bshale\b|\bslate\b|\bsh\b(?!\s*&\s*g)/i, cat: "rock" },
    { id: "siltstone", re: /\bsiltstone\b|\bquartzite\b|\bchert\b/i, cat: "rock" },
    { id: "igneous", re: /granite|marble|basalt|gneiss|schist|conglomerate|argillite|\bcoal\b/i, cat: "rock" },
    { id: "bedrock_abbrev", re: /\b(ls|lm|dl|dol)\b/i, cat: "rock" },
    { id: "topsoil", re: /^top\s*soil$|^topsoil$|^fill$|^soil$|^surface$|^top$|^dirt$|fill\s*dirt|surface\s*fill|blanket|overburden|top\s*dirt|black\s*dirt|hard\s*gray\s*soil|gray\s*soil/i, cat: "overburden" },
    { id: "sg", re: /\bs\s*&\s*g\b|\bsg\b|sand\s*\/\s*g|sand\s*grav|sand\s+and\s+grav|s\s+and\s+g/i, cat: "unconsolidated" },
    { id: "gravel", re: /\bgrav\b|\bgravel\b|pea\s*grav|gravelly|pea\s*stone/i, cat: "unconsolidated" },
    { id: "water_bearing", re: /water\s*b\.?|water\s*bearing|water\s*grav|water\s*zone|producing|water\s*vein|gravel\s*vein|sand\s*vein/i, cat: "unconsolidated" },
    { id: "drift", re: /glacial\s*drift|\bdrift\b|outwash|esker|kame|\btill\b|alluv|terrace/i, cat: "unconsolidated" },
    { id: "sand", re: /\bsand\b|\bsa\b|\bgr\b(?!\s*ls)|\bfine\s+sand\b|\bcoarse\s+sand\b|\bmedium\s+sand\b/i, cat: "unconsolidated" },
    { id: "clay", re: /\bclay\b|\bsilt\b|\bmuck\b|\bpeat\b|\bloam\b|hard\s*pan|hardpan|caliche|sandy\s*clay|clayey/i, cat: "mixed" },
    { id: "generic_rock", re: /\brock\b|\bstone\b/i, cat: "rock" },
  ];

  function classifyVersion() {
    try {
      if (typeof process !== "undefined" && process.env && process.env.NEXT_PUBLIC_DNR_CLASSIFY_VERSION === "v1")
        return "v1";
    } catch (e) {}
    try {
      var q = new URLSearchParams(global.location && global.location.search || "");
      if (q.get("classify") === "v1" || q.get("dnr_classify") === "v1") return "v1";
    } catch (e2) {}
    if (global.DNR_CLASSIFY_VERSION === "v1") return "v1";
    return "v2";
  }

  function positiveFt(v) {
    if (v == null || v === "") return null;
    var n = parseFloat(String(v).replace(/,/g, "").replace(/[^\d.\-]/g, ""));
    if (!isFinite(n) || n <= 0) return null;
    return n;
  }

  function formationCategoryForName(name) {
    var raw = (name || "").trim();
    if (!raw) return { category: "ignore", ruleId: "empty" };
    if (DRY_RE.test(raw)) return { category: "ignore", ruleId: "dry" };
    for (var i = 0; i < PATTERN_RULES.length; i++) {
      if (PATTERN_RULES[i].re.test(raw))
        return { category: PATTERN_RULES[i].cat, ruleId: PATTERN_RULES[i].id };
    }
    return { category: "unknown", ruleId: "none" };
  }

  function isSandstoneFamily(fm) {
    return SANDSTONE_FAMILY_RE.test(fm || "");
  }

  var WATER_BEARING_MATERIAL_RE =
    /water\s*b\.?|water\s*bearing|\bwet\b|producing|water\s*vein|gravel\s*vein|sand\s*vein|\bgrav|\bgravel|pea\s*stone|\bs\s*&\s*g\b|\bsg\b|sand\s*\/\s*g|sand\s*grav|sand\s+and\s+grav|s\s+and\s+g|outwash|esker|kame|glacial\s*drift|\bdrift\b/i;
  var LOOSE_SAND_WORD_RE =
    /\bsand\b|\bsa\b|\bfine\s+sand\b|\bcoarse\s+sand\b|\bmedium\s+sand\b/i;

  function isWaterBearingMaterial(fm) {
    if (!fm || isSandstoneFamily(fm)) return false;
    return WATER_BEARING_MATERIAL_RE.test(fm);
  }

  function isNonWaterBearingSand(fm) {
    if (!fm || isSandstoneFamily(fm)) return false;
    if (isWaterBearingMaterial(fm)) return false;
    if (/sandy\s*clay|clayey\s*sand|sand\s*rock|sandstone/i.test(fm)) return false;
    return LOOSE_SAND_WORD_RE.test(fm);
  }

  function layerCountsTowardUncon(category, fm) {
    if (isSandstoneFamily(fm)) return false;
    if (isNonWaterBearingSand(fm)) return false;
    if (isWaterBearingMaterial(fm)) return true;
    if (category === "unconsolidated") return !isNonWaterBearingSand(fm);
    if (category === "rock" || category === "overburden" || category === "ignore") return false;
    if (category === "mixed")
      return /grav|gravel|\bsg\b|s\s*&\s*g|sand\s*grav|s\s+and\s+g/i.test(fm || "");
    var l = (fm || "").toLowerCase();
    if (/lime|dolomite|shale|slate|sandstone|siltstone|bedrock|granite|marble|\brock\b/i.test(l) &&
        !/sand\s+and|gravel|drift|sa\b|gr\b|sg\b|outwash|till/i.test(l))
      return false;
    return /grav|gravel|\bsg\b|s\s*&\s*g|sand\s*grav|water\s*b\.?|water\s*bearing|outwash|drift|\bwet\b|\bgr\b/i.test(l);
  }

  function layerIsRockTop(category, fm) {
    if (isSandstoneFamily(fm) || category === "rock") return true;
    if (category === "unconsolidated" || category === "overburden" || category === "ignore") return false;
    var l = (fm || "").toLowerCase();
    return /lime|dolomite|shale|slate|sandstone|siltstone|bedrock|granite|marble|\brock\b/i.test(l) &&
      l.indexOf("sand and") < 0 && l.indexOf("gravel") < 0;
  }

  /** C=clay/hardpan/soil, G=water-bearing sand/gravel, S=dry sand, R=rock, ?=unknown */
  function layerCodeFor(category, fm, countsTowardUncon) {
    if (category === "ignore") return "?";
    if (category === "rock" || isSandstoneFamily(fm)) return "R";
    if (isWaterBearingMaterial(fm)) return "G";
    if (isNonWaterBearingSand(fm)) return "S";
    if (category === "unconsolidated" || countsTowardUncon) return "G";
    if (
      category === "overburden" ||
      category === "mixed" ||
      /clay|hard\s*pan|hardpan|silt|muck|peat|loam|soil|dirt|fill|till/i.test(fm || "")
    )
      return "C";
    return "?";
  }

  function buildLayerStackLabel(layers) {
    var segs = [];
    for (var i = 0; i < layers.length; i++) {
      var L = layers[i];
      if (L.code === "?" && L.category === "ignore") continue;
      if (L.topFt == null || L.bottomFt == null) continue;
      if (!(L.bottomFt > L.topFt)) continue;
      var last = segs.length ? segs[segs.length - 1] : null;
      if (last && last.code === L.code && Math.abs(last.bot - L.topFt) < 0.51) {
        last.bot = Math.max(last.bot, L.bottomFt);
      } else {
        segs.push({ code: L.code, top: L.topFt, bot: L.bottomFt });
      }
    }
    if (!segs.length) return "";
    return segs
      .map(function (s) {
        return s.code + Math.round(s.top) + "-" + Math.round(s.bot);
      })
      .join(" / ");
  }

  /** When S matches a G span (same depths / contained), keep G only. */
  function preferGOverMatchingS(chips) {
    if (!chips.length) return chips;
    var gChips = chips.filter(function (c) { return c.code === "G"; });
    if (!gChips.length) return chips;
    var kept = chips.filter(function (c) {
      if (c.code !== "S") return true;
      for (var i = 0; i < gChips.length; i++) {
        var g = gChips[i];
        var sameTop = Math.abs(c.topFt - g.topFt) <= 1;
        var sameBot = Math.abs(c.bottomFt - g.bottomFt) <= 1;
        var sameThick = c.thicknessFt === g.thicknessFt;
        if ((sameTop && sameBot) || (sameTop && sameThick)) return false;
        if (c.topFt >= g.topFt - 0.5 && c.bottomFt <= g.bottomFt + 0.5) return false;
      }
      return true;
    });
    var gIdx = 0;
    var sIdx = 0;
    return kept.map(function (c) {
      var index = c.code === "G" ? ++gIdx : ++sIdx;
      return {
        code: c.code,
        index: index,
        topFt: c.topFt,
        bottomFt: c.bottomFt,
        thicknessFt: c.thicknessFt,
      };
    });
  }

  /** S + G face chips in hole order; consecutive same-code merge. G wins over matching S. */
  function faceChipsFromLayers(layers) {
    var segs = [];
    for (var i = 0; i < layers.length; i++) {
      var L = layers[i];
      if (L.code !== "G" && L.code !== "S") continue;
      if (L.topFt == null || L.bottomFt == null) continue;
      if (!(L.bottomFt > L.topFt)) continue;
      var last = segs.length ? segs[segs.length - 1] : null;
      if (last && last.code === L.code && Math.abs(last.bot - L.topFt) < 0.51) {
        last.bot = Math.max(last.bot, L.bottomFt);
      } else {
        segs.push({ code: L.code, top: L.topFt, bot: L.bottomFt });
      }
    }
    var gIdx = 0;
    var sIdx = 0;
    var raw = segs.map(function (s) {
      var top = Math.round(s.top);
      var bot = Math.round(s.bot);
      var rawTh = bot - top;
      var index = s.code === "G" ? ++gIdx : ++sIdx;
      return {
        code: s.code,
        index: index,
        topFt: top,
        bottomFt: bot,
        thicknessFt: rawTh > 0 ? rawTh : Math.max(1, Math.round(s.bot - s.top)),
      };
    });
    return preferGOverMatchingS(raw);
  }

  /** Water-bearing G intervals only. */
  function veinIntervalsFromLayers(layers) {
    return faceChipsFromLayers(layers)
      .filter(function (c) { return c.code === "G"; })
      .map(function (c, idx) {
        return {
          index: idx + 1,
          topFt: c.topFt,
          bottomFt: c.bottomFt,
          thicknessFt: c.thicknessFt,
        };
      });
  }

  function veinBottomsFromLayers(layers) {
    return veinIntervalsFromLayers(layers)
      .map(function (v) { return v.bottomFt; })
      .filter(function (n) { return n > 0; });
  }

  /** S1 5·G1 2 — dry sand + water-bearing aquifers in depth order. */
  function faceSetLabelFromChips(chips) {
    if (!chips.length) return null;
    return chips
      .map(function (c) { return c.code + c.index + " " + c.thicknessFt; })
      .join(" / ");
  }

  /** True when depth falls inside a sand/gravel (S or G) lith interval. */
  function depthInsideSandGravelInterval(depthFt, layers) {
    if (!(depthFt > 0) || !layers || !layers.length) return false;
    for (var i = 0; i < layers.length; i++) {
      var L = layers[i];
      if (L.code !== "G" && L.code !== "S") continue;
      if (L.topFt == null || L.bottomFt == null) continue;
      if (!(L.bottomFt > L.topFt)) continue;
      if (depthFt > L.topFt + 0.5 && depthFt < L.bottomFt - 0.5) return true;
    }
    return false;
  }

  /**
   * Keep only S/G face chips above rock top; clip straddlers; re-index.
   * Dom 2026-07-23: rock top cannot come before gravel on the face.
   */
  function faceChipsAboveRockTop(chips, rockTopFt) {
    if (rockTopFt == null || !(rockTopFt > 0)) return chips;
    var rt = rockTopFt;
    var clipped = [];
    for (var i = 0; i < chips.length; i++) {
      var c = chips[i];
      if (c.topFt >= rt - 0.5) continue;
      var bot = Math.min(c.bottomFt, rt);
      var top = c.topFt;
      if (!(bot > top)) continue;
      clipped.push({
        code: c.code,
        index: c.index,
        topFt: Math.round(top),
        bottomFt: Math.round(bot),
        thicknessFt: Math.max(1, Math.round(bot - top)),
      });
    }
    var gIdx = 0;
    var sIdx = 0;
    return clipped.map(function (c) {
      var index = c.code === "G" ? ++gIdx : ++sIdx;
      return {
        code: c.code,
        index: index,
        topFt: c.topFt,
        bottomFt: c.bottomFt,
        thicknessFt: c.thicknessFt,
      };
    });
  }

  /** Defensive: S/G first, R always last on face label. */
  function ensureRockChipLastOnFaceLabel(label) {
    if (!label) return null;
    var raw = String(label).trim();
    if (!raw) return null;
    var parts = raw.split(/\s*[·/]\s*/).map(function (s) { return s.trim(); }).filter(Boolean);
    if (!parts.length) return null;
    var rock = [];
    var other = [];
    for (var i = 0; i < parts.length; i++) {
      var p = parts[i];
      if (/^R@?\d+$/i.test(p)) rock.push(p.replace(/^R@/i, "R"));
      else other.push(p);
    }
    if (!rock.length) return other.join(" / ");
    return other.concat(rock).join(" / ");
  }

  function veinSetLabelFromIntervals(intervals) {
    if (!intervals.length) return null;
    return intervals
      .map(function (v) { return "G" + v.index + " " + v.thicknessFt; })
      .join(" / ");
  }

  function isGravelSetLabel(label) {
    if (!label) return false;
    return /(?:^|[·/])\s*G@/i.test(String(label)) || /(?:^|[·/])\s*G\d+(\s+\d+)?/i.test(String(label));
  }

  function isSandSetLabel(label) {
    if (!label) return false;
    return /(?:^|[·/])\s*S\d+(\s+\d+)?/i.test(String(label));
  }

  function isMapFaceSetLabel(label) {
    if (!label) return false;
    return isRockSetLabel(label) || isGravelSetLabel(label) || isSandSetLabel(label);
  }

  function aquiferClass(aq) {
    var s = (aq || "").trim();
    if (!s) return "unknown";
    if (/^estimated\b/i.test(s)) return "unknown";
    if (ROCK_AQ_RE.test(s) && !/unconsolidated|sand\s*(and|&)?\s*grav/i.test(s)) return "bedrock";
    if (UNCON_AQ_RE.test(s) && !/sandstone|siltstone/i.test(s)) return "unconsolidated";
    if (ROCK_AQ_RE.test(s)) return "bedrock";
    return "unknown";
  }

  function primaryAquifer(w) {
    var keys = ["aquifer", "aquifer_type", "aquifer_desc", "primary_aquifer"];
    for (var i = 0; i < keys.length; i++) {
      if (w[keys[i]] != null && String(w[keys[i]]).trim()) return String(w[keys[i]]).trim();
    }
    return "";
  }

  function isEstimatedLocation(w) {
    var aq = primaryAquifer(w).toLowerCase();
    var lt = String(w.loc_type || w.location_type || "").toLowerCase();
    return aq.indexOf("estimated") >= 0 || lt.indexOf("estimated") >= 0;
  }

  function parseLithLayers(w) {
    var raw = w.lithology_json || w.lithology || w.well_log_json || "";
    if (raw == null || String(raw).trim() === "") return [];
    try {
      var j = typeof raw === "string" ? JSON.parse(String(raw).trim()) : raw;
      if (typeof j === "string") {
        var t = j.trim();
        if (t.charAt(0) === "[" || t.charAt(0) === "{") j = JSON.parse(t);
      }
      if (Array.isArray(j)) return j.filter(function (x) { return x && typeof x === "object"; });
      if (j && typeof j === "object") {
        var keys = ["layers", "intervals", "data", "well_log", "Lithology", "records"];
        for (var i = 0; i < keys.length; i++) {
          if (Array.isArray(j[keys[i]])) return j[keys[i]].filter(function (x) { return x && typeof x === "object"; });
        }
      }
    } catch (e) {}
    return [];
  }

  function formationName(layer) {
    var keys = ["formation", "Formation", "material", "Material", "lithology", "description", "strata"];
    for (var i = 0; i < keys.length; i++) {
      if (layer[keys[i]] != null && String(layer[keys[i]]).trim()) return String(layer[keys[i]]).trim();
    }
    return "";
  }

  function layerTopBottom(layer, prevBot) {
    function pd(v) {
      if (v == null || v === "") return NaN;
      return parseFloat(String(v).replace(/,/g, "").replace(/[^\d.\-]/g, ""));
    }
    var top = pd(layer.top != null ? layer.top : layer.Top != null ? layer.Top : layer.from != null ? layer.from : layer.From != null ? layer.From : layer.depth_top != null ? layer.depth_top : layer.depth_from);
    var bot = pd(layer.bottom != null ? layer.bottom : layer.Bottom != null ? layer.Bottom : layer.to != null ? layer.to : layer.To != null ? layer.To : layer.depth_bottom != null ? layer.depth_bottom : layer.depth_to);
    if (isNaN(top) && !isNaN(prevBot)) top = prevBot;
    return { top: top, bot: bot };
  }

  /** R20 = top of rock (lithology), not casing shoe. No @ sign. */
  function rockSetLabelFromTop(rockTopFt, casingLengthFt) {
    if (rockTopFt != null && rockTopFt > 0) return "R" + Math.round(rockTopFt);
    if (casingLengthFt != null && casingLengthFt > 0) return "R" + Math.round(casingLengthFt);
    return null;
  }

  function isRockSetLabel(label) {
    if (!label) return false;
    return /(?:^|[·/])\s*R@?\d+/i.test(String(label));
  }

  function analyzeConstruction(w, rockTopFt, formationHint) {
    var reasons = [];
    var casingLengthFt = positiveFt(w.casing_length);
    var screenLengthFt = positiveFt(w.screen_length);
    var screenDiam = positiveFt(w.screen_diam != null ? w.screen_diam : w.screen_diameter);
    var totalDepthFt = positiveFt(w.depth);
    var hasScreen = (screenLengthFt != null && screenLengthFt > 0) || (screenDiam != null && screenDiam > 0);
    var noScreen = !hasScreen;
    var openHoleBelowCasingFt = null;
    if (casingLengthFt != null && totalDepthFt != null)
      openHoleBelowCasingFt = Math.round(Math.max(0, totalDepthFt - casingLengthFt) * 10) / 10;

    var casingIntoRockFt = null;
    var casingAboveRockFt = null;
    if (casingLengthFt != null && rockTopFt != null && rockTopFt > 0) {
      var delta = casingLengthFt - rockTopFt;
      if (delta >= 0) {
        casingIntoRockFt = Math.round(delta * 10) / 10;
        casingAboveRockFt = 0;
      } else {
        casingAboveRockFt = Math.round(-delta * 10) / 10;
        casingIntoRockFt = 0;
      }
    }

    var kind = "unknown";
    var producingSetFt = null;
    var setLabel = null;

    if (hasScreen) {
      kind = "screen_set";
      reasons.push("construction:screen_present");
      if (casingLengthFt != null) {
        setLabel = "G@" + Math.round(casingLengthFt);
        producingSetFt = Math.round(casingLengthFt + (screenLengthFt || 0) / 2);
      }
    } else if (noScreen && rockTopFt != null && rockTopFt > 0 && casingLengthFt != null && totalDepthFt != null) {
      var into = casingIntoRockFt != null ? casingIntoRockFt : -999;
      var above = casingAboveRockFt != null ? casingAboveRockFt : 999;
      var open = openHoleBelowCasingFt != null ? openHoleBelowCasingFt : 0;
      var casingNearRock =
        (into >= 0 && into <= CASING_INTO_ROCK_MAX_FT) ||
        (above >= 0 && above <= CASING_ROCK_ABOVE_TOL_FT && into === 0);
      if (open < MIN_OPEN_HOLE_ROCK_FT) {
        reasons.push("construction:reject_rock_no_open_hole casing=" + casingLengthFt + " depth=" + totalDepthFt + " rock=" + rockTopFt);
      } else if (casingNearRock || into > CASING_INTO_ROCK_MAX_FT) {
        kind = "rock_open_hole";
        reasons.push("construction:rock_open_hole casing=" + casingLengthFt + " rock_top=" + rockTopFt + " open_hole=" + open);
        setLabel = rockSetLabelFromTop(rockTopFt, casingLengthFt);
        producingSetFt = Math.round(rockTopFt != null && rockTopFt > 0 ? rockTopFt : casingLengthFt);
        if (rockTopFt != null && Math.round(rockTopFt) !== Math.round(casingLengthFt)) {
          reasons.push("construction:R_at_rock_top_not_casing rock=" + Math.round(rockTopFt) + " casing=" + Math.round(casingLengthFt));
        }
      }
    }

    // Dom: R@ = top of rock, never casing when rock top known
    if (formationHint === "rock") {
      var rLab0 = rockSetLabelFromTop(rockTopFt, casingLengthFt);
      if (rLab0) {
        setLabel = rLab0;
        producingSetFt = rockTopFt != null && rockTopFt > 0
          ? Math.round(rockTopFt)
          : casingLengthFt != null ? Math.round(casingLengthFt) : producingSetFt;
        if (kind === "screen_set") reasons.push("construction:set_label_rock_overrides_screen_G");
      }
    } else if (formationHint === "unconsolidated" && casingLengthFt != null && !setLabel) {
      setLabel = "G@" + Math.round(casingLengthFt);
      producingSetFt = Math.round(casingLengthFt);
    }
    if (formationHint === "unknown" && kind === "screen_set") {
      setLabel = null;
      producingSetFt = null;
      reasons.push("construction:no_G_label_without_uncon_formation");
    }

    return {
      casingLengthFt: casingLengthFt,
      screenLengthFt: screenLengthFt,
      screenDiam: screenDiam,
      hasScreen: hasScreen,
      noScreen: noScreen,
      totalDepthFt: totalDepthFt,
      openHoleBelowCasingFt: openHoleBelowCasingFt,
      casingIntoRockFt: casingIntoRockFt,
      casingAboveRockFt: casingAboveRockFt,
      kind: kind,
      producingSetFt: producingSetFt,
      setLabel: setLabel,
      reasons: reasons,
    };
  }

  function classifyFormationFromWell(w) {
    var reasons = [];
    var layersRaw = parseLithLayers(w);
    var layers = [];
    var prevBot = NaN;
    var rockTop = null;
    var wbSum = 0;
    var onlyOverburdenUncon = true;

    for (var i = 0; i < layersRaw.length; i++) {
      var L = layersRaw[i];
      var fm = formationName(L);
      var tb = layerTopBottom(L, prevBot);
      if (!isNaN(tb.bot)) prevBot = tb.bot;
      var fc = formationCategoryForName(fm);
      var thick = !isNaN(tb.top) && !isNaN(tb.bot) && tb.bot > tb.top ? tb.bot - tb.top : null;
      var ctu = layerCountsTowardUncon(fc.category, fm);
      var isRock = layerIsRockTop(fc.category, fm);
      if (rockTop == null && isRock && !isNaN(tb.top) && tb.top >= 0) rockTop = tb.top;
      if (ctu && thick != null && thick > 0) {
        wbSum += thick;
        if (fc.category !== "overburden") onlyOverburdenUncon = false;
      }
      var code = layerCodeFor(fc.category, fm, ctu);
      layers.push({
        index: i, formation: fm, topFt: isNaN(tb.top) ? null : tb.top,
        bottomFt: isNaN(tb.bot) ? null : tb.bot, thicknessFt: thick,
        category: fc.category, code: code, ruleId: fc.ruleId, countsTowardUncon: ctu, isRockTopSignal: isRock,
      });
    }

    var lithHadRockSignal = false;
    for (var ri = 0; ri < layers.length; ri++) {
      if (layers[ri].isRockTopSignal) { lithHadRockSignal = true; break; }
    }
    var hasLithLayers = layersRaw.length > 0;
    var totalDepthForSane = positiveFt(w.depth);

    var chunkRock = positiveFt(w.rock_start_ft) || positiveFt(w.depth_bedrock);
    if (chunkRock != null) {
      var chunkInSg = depthInsideSandGravelInterval(chunkRock, layers);
      if (rockTop == null) {
        var equalsDepth = totalDepthForSane != null && Math.abs(chunkRock - totalDepthForSane) < 0.51;
        if (hasLithLayers && !lithHadRockSignal && equalsDepth) {
          reasons.push("reject_chunk_rock_top_equals_depth_no_lith_rock:" + chunkRock);
        } else if (hasLithLayers && !lithHadRockSignal) {
          reasons.push("reject_chunk_rock_top_no_lith_rock:" + chunkRock);
        } else if (chunkInSg) {
          reasons.push("reject_chunk_rock_top_inside_sg:" + chunkRock);
        } else {
          rockTop = chunkRock;
          reasons.push("rock_top_from_chunk:" + chunkRock);
        }
      } else if (chunkInSg) {
        reasons.push("reject_chunk_rock_top_inside_sg_keep_lith:" + chunkRock);
      } else if (chunkRock < rockTop) {
        rockTop = chunkRock;
        reasons.push("rock_top_min_chunk:" + chunkRock);
      }
    }

    var vein = positiveFt(w.vein_size_ft) || positiveFt(w.gravel_thickness_ft);
    if (vein != null && vein > 0 && wbSum <= 0) {
      var rockCol = positiveFt(w.rock_start_ft) || positiveFt(w.depth_bedrock);
      var equalsRockCol = rockCol != null && Math.abs(vein - rockCol) < 0.51;
      var exceedsOrEqualsDepth = totalDepthForSane != null && vein >= totalDepthForSane;
      if (equalsRockCol) {
        reasons.push("reject_vein_column_equals_rock_start:" + vein);
      } else if (exceedsOrEqualsDepth) {
        reasons.push("reject_vein_column_vs_depth:" + vein);
      } else if (hasLithLayers && wbSum <= 0) {
        reasons.push("reject_vein_column_no_sand_gravel_lithology:" + vein);
      } else {
        wbSum = vein;
        onlyOverburdenUncon = false;
        reasons.push("uncon_from_vein_column:" + vein);
      }
    }

    var aq = primaryAquifer(w);
    var aqCls = aquiferClass(aq);
    if (aqCls !== "unknown") reasons.push("aquifer_text:" + aqCls);

    var wellType = "unknown";
    var wb = wbSum > 0 ? Math.round(wbSum) : null;
    var hasRealUncon = wb != null && wb > 0;
    var construction = analyzeConstruction(w, rockTop, null);
    reasons = reasons.concat(construction.reasons);

    if (construction.kind === "rock_open_hole") {
      wellType = "rock";
      reasons.push("decide:rock_by_construction");
    }

    if (wellType === "unknown" && construction.kind === "screen_set") {
      if (hasRealUncon) {
        wellType = "unconsolidated";
        reasons.push("decide:uncon_by_screen_and_thickness:" + wb);
      } else if (rockTop != null && rockTop > 0) {
        reasons.push("screen_present_but_no_sand_gravel_prefer_rock_path");
      } else if (!hasLithLayers) {
        wellType = "unconsolidated";
        reasons.push("decide:uncon_by_screen_no_lithology");
      } else {
        reasons.push("decide:skip_screen_uncon_clay_or_non_water_bearing_lithology");
      }
    }

    if (wellType === "unknown") {
      if (hasRealUncon) {
        wellType = "unconsolidated";
        reasons.push("uncon_thickness_ft:" + wb);
      } else if (rockTop != null && rockTop > 0) {
        var screenBlocksRock = construction.hasScreen && hasRealUncon;
        if (screenBlocksRock) {
          reasons.push("reject:rock_top_screen_with_uncon");
        } else if (construction.casingLengthFt != null && construction.openHoleBelowCasingFt != null &&
            construction.openHoleBelowCasingFt < MIN_OPEN_HOLE_ROCK_FT && construction.noScreen) {
          reasons.push("reject:rock_top_without_open_hole_below_casing");
        } else if (construction.noScreen && construction.openHoleBelowCasingFt != null &&
                   construction.openHoleBelowCasingFt >= MIN_OPEN_HOLE_ROCK_FT) {
          wellType = "rock";
          reasons.push("rock_top_ft:" + Math.round(rockTop) + "_with_open_hole:" + construction.openHoleBelowCasingFt);
        } else if (construction.hasScreen && !hasRealUncon && construction.casingLengthFt != null &&
                   construction.totalDepthFt != null &&
                   (construction.totalDepthFt > rockTop + MIN_OPEN_HOLE_ROCK_FT || construction.casingLengthFt >= rockTop)) {
          wellType = "rock";
          reasons.push("rock_top_ft:" + Math.round(rockTop) + "_screen_ignored_no_uncon");
        } else if (construction.casingLengthFt == null && construction.totalDepthFt != null &&
                   construction.totalDepthFt > rockTop + MIN_OPEN_HOLE_ROCK_FT) {
          wellType = "rock";
          reasons.push("rock_top_ft:" + Math.round(rockTop) + "_depth_below_rock:" + construction.totalDepthFt);
        } else {
          var lithBotMax = null;
          for (var bi = 0; bi < layers.length; bi++) {
            if (layers[bi].bottomFt != null && isFinite(layers[bi].bottomFt)) {
              lithBotMax = lithBotMax == null ? layers[bi].bottomFt : Math.max(lithBotMax, layers[bi].bottomFt);
            }
          }
          if (!hasRealUncon && lithBotMax != null && lithBotMax > rockTop + MIN_OPEN_HOLE_ROCK_FT) {
            wellType = "rock";
            reasons.push("rock_from_lithology_into_rock top=" + Math.round(rockTop) + " bot=" + Math.round(lithBotMax));
          } else {
            reasons.push("rock_top_seen:" + Math.round(rockTop) + "_insufficient_construction");
          }
        }
      }
    }

    if (wellType === "unconsolidated" && construction.kind === "rock_open_hole" && (wb || 0) < MIN_UNCON_OVERRIDE_FT) {
      wellType = "rock";
      reasons.push("override:rock_construction_beats_thin_uncon");
    }

    if (wellType === "unconsolidated" && aqCls === "bedrock" && (wb || 0) < MIN_UNCON_OVERRIDE_FT && rockTop != null) {
      if (construction.hasScreen && hasRealUncon) {
        reasons.push("override:skipped_bedrock_aq_because_screen_with_uncon");
      } else {
        var depthPastRock = construction.totalDepthFt != null && construction.totalDepthFt > rockTop + MIN_OPEN_HOLE_ROCK_FT;
        var openPast = (construction.openHoleBelowCasingFt || 0) >= MIN_OPEN_HOLE_ROCK_FT;
        var sealed = construction.noScreen && construction.casingLengthFt != null && construction.openHoleBelowCasingFt != null &&
          construction.openHoleBelowCasingFt < MIN_OPEN_HOLE_ROCK_FT;
        if (sealed) reasons.push("override:skipped_bedrock_aq_no_open_hole");
        else if (construction.kind === "rock_open_hole" || openPast || depthPastRock ||
                 onlyOverburdenUncon || (construction.hasScreen && !hasRealUncon)) {
          wellType = "rock";
          reasons.push("override:bedrock_aq_thin_uncon_with_rock_completion");
        }
      }
    }

    if (wellType === "rock" && construction.hasScreen && hasRealUncon) {
      wellType = "unconsolidated";
      reasons.push("override:screen_with_uncon_thickness_not_rock");
    } else if (wellType === "rock" && construction.hasScreen && !hasRealUncon) {
      reasons.push("screen_ignored_no_sand_gravel_keep_rock");
    }

    if (wellType === "unknown") {
      if (aqCls === "unconsolidated") {
        if (hasRealUncon) {
          wellType = "unconsolidated";
          reasons.push("fallback_aquifer_unconsolidated_with_thickness");
        } else if (!hasLithLayers) {
          wellType = "unconsolidated";
          reasons.push("fallback_aquifer_unconsolidated_no_lithology");
        } else {
          reasons.push("fallback:skip_aquifer_uncon_no_sand_gravel_in_lithology");
        }
      } else if (aqCls === "bedrock") {
        if (construction.hasScreen && hasRealUncon) {
          wellType = "unconsolidated";
          reasons.push("fallback:bedrock_aq_but_screen_with_uncon");
        } else if (construction.casingLengthFt != null && construction.totalDepthFt != null &&
                   (construction.openHoleBelowCasingFt || 0) < MIN_OPEN_HOLE_ROCK_FT && construction.noScreen) {
          reasons.push("fallback:bedrock_aq_but_no_open_hole_rejected");
        } else {
          wellType = "rock";
          reasons.push("fallback_aquifer_bedrock");
        }
      }
    }

    if (wellType === "unknown" && construction.hasScreen) {
      if (hasRealUncon || !hasLithLayers) {
        wellType = "unconsolidated";
        reasons.push("fallback_screen_present");
      } else {
        reasons.push("fallback:skip_screen_without_sand_gravel_lithology");
      }
    }

    var constructionFinal = analyzeConstruction(w, rockTop, wellType);
    construction.setLabel = constructionFinal.setLabel;
    construction.producingSetFt = constructionFinal.producingSetFt;
    if (wellType === "rock" && construction.kind === "screen_set") {
      if (constructionFinal.kind === "rock_open_hole") construction.kind = "rock_open_hole";
    } else if (construction.kind === "unknown") {
      construction.kind = constructionFinal.kind;
    }
    if (wellType !== "unconsolidated" && isGravelSetLabel(construction.setLabel)) {
      if (wellType === "rock") {
        var rLab1 = rockSetLabelFromTop(rockTop, construction.casingLengthFt);
        if (rLab1) {
          construction.setLabel = rLab1;
          construction.producingSetFt = rockTop != null && rockTop > 0
            ? Math.round(rockTop)
            : construction.casingLengthFt != null
              ? Math.round(construction.casingLengthFt)
              : null;
        } else {
          construction.setLabel = null;
          construction.producingSetFt = null;
        }
      } else {
        construction.setLabel = null;
        construction.producingSetFt = null;
        reasons.push("strip_G_label_non_uncon_formation");
      }
    }
    // Force rock map chip to rock top (not casing) for consistency
    if (wellType === "rock") {
      var rLab2 = rockSetLabelFromTop(rockTop, construction.casingLengthFt);
      if (rLab2) {
        construction.setLabel = rLab2;
        if (rockTop != null && rockTop > 0) construction.producingSetFt = Math.round(rockTop);
      }
    }
    if (wellType === "unconsolidated" && !hasRealUncon && hasLithLayers &&
        isGravelSetLabel(construction.setLabel)) {
      construction.setLabel = null;
      construction.producingSetFt = null;
      reasons.push("strip_G_label_no_sand_gravel_thickness");
    }

    var layerStackLabel = buildLayerStackLabel(layers);
    var faceChipsAll = faceChipsFromLayers(layers);
    // Dom 2026-07-23: gravel/sand on face must sit ABOVE rock top
    var faceChips =
      wellType === "rock"
        ? faceChipsAboveRockTop(faceChipsAll, rockTop)
        : faceChipsAll;
    var veinIntervals = veinIntervalsFromLayers(layers).filter(function (v) {
      if (wellType !== "rock" || rockTop == null || !(rockTop > 0)) return true;
      return v.topFt < rockTop - 0.5;
    });
    var veinBottomsFt = veinIntervals
      .map(function (v) { return v.bottomFt; })
      .filter(function (n) { return n > 0; });
    var veinThicknessesFt = veinIntervals.map(function (v) { return v.thicknessFt; });
    var veinSetLabel = faceSetLabelFromChips(faceChips);
    var hasG = faceChips.some(function (c) { return c.code === "G"; });
    var hasS = faceChips.some(function (c) { return c.code === "S"; });
    var rockChip = rockSetLabelFromTop(rockTop, construction.casingLengthFt);
    if (veinSetLabel && faceChips.length >= 1) {
      if (wellType === "rock" && rockChip) {
        construction.setLabel = ensureRockChipLastOnFaceLabel(
          veinSetLabel + " / " + rockChip
        );
        reasons.push("face_S_G_with_rock:" + construction.setLabel);
      } else if (wellType === "unconsolidated" || hasG || hasS) {
        construction.setLabel = veinSetLabel;
        if (hasG) {
          construction.producingSetFt = veinBottomsFt.length
            ? veinBottomsFt[veinBottomsFt.length - 1]
            : construction.producingSetFt;
        }
        reasons.push(
          faceChips.length >= 2
            ? "multi_face_thickness_label:" + veinSetLabel
            : "face_thickness_label:" + veinSetLabel
        );
      }
    } else if (
      wellType === "unconsolidated" &&
      !veinSetLabel &&
      construction.screenLengthFt != null &&
      construction.screenLengthFt > 0 &&
      isGravelSetLabel(construction.setLabel)
    ) {
      var g1s = "G1 " + Math.round(construction.screenLengthFt);
      construction.setLabel = g1s;
      reasons.push("screen_thickness_proxy_label:" + g1s);
    } else if (
      wellType === "unconsolidated" &&
      !veinSetLabel &&
      isGravelSetLabel(construction.setLabel) &&
      String(construction.setLabel).indexOf("G@") === 0
    ) {
      construction.setLabel = null;
      reasons.push("strip_legacy_G_at_set_without_aquifer_thickness");
    }

    var confidence = "low";
    if (construction.kind === "rock_open_hole" || construction.kind === "screen_set")
      confidence = layersRaw.length > 0 || rockTop != null || (wb != null && wb > 0) ? "high" : "medium";
    else if (layersRaw.length > 0 && (wb != null || rockTop != null))
      confidence = aqCls !== "unknown" ? "high" : "medium";
    else if (aqCls !== "unknown") confidence = "medium";
    else if (wellType !== "unknown") confidence = "low";

    return {
      formationClass: wellType,
      rockTopFt: rockTop != null ? Math.round(rockTop) : null,
      unconsolidatedFt: wb,
      layers: layers,
      layerStackLabel: layerStackLabel,
      veinBottomsFt: veinBottomsFt,
      veinThicknessesFt: veinThicknessesFt,
      veinSetLabel: veinSetLabel,
      confidence: confidence,
      reasons: reasons,
      rulesetId: RULESET,
      construction: construction,
    };
  }

  function isDrySimple(w) {
    return primaryAquifer(w).toLowerCase().indexOf("dry") >= 0;
  }

  function isBucketSimple(w) {
    var blob = [w.loc_type, w.well_type, w.pump_type, w.well_use, w.notes].join(" ").toLowerCase();
    return blob.indexOf("bucket") >= 0 || blob.indexOf("hand dug") >= 0 || blob.indexOf("dug well") >= 0;
  }

  function classifyWellDual(w) {
    if (classifyVersion() === "v1") {
      // Minimal v1: estimated exclusive; aquifer uncon; else rock
      if (isDrySimple(w)) return { markerCategory: "dry", locationQuality: "verified", formationClass: "unknown", displayLabel: "Dry", setLabel: null, special: "dry" };
      if (isBucketSimple(w)) return { markerCategory: "bucket", locationQuality: "verified", formationClass: "unknown", displayLabel: "Bucket", setLabel: null, special: "bucket" };
      var est = isEstimatedLocation(w);
      if (est) return { markerCategory: "estimated", locationQuality: "estimated", formationClass: "unknown", displayLabel: "Est", setLabel: null, special: null };
      var aq = primaryAquifer(w).toLowerCase();
      var uncon = /unconsolidated|sand|gravel/.test(aq) && !/bedrock|limestone|sandstone|shale|dolomite/.test(aq);
      return {
        markerCategory: uncon ? "unconsolidated" : "rock",
        locationQuality: "verified",
        formationClass: uncon ? "unconsolidated" : "rock",
        displayLabel: uncon ? "G" : "R",
        setLabel: null,
        special: null,
        rulesetId: "dnr-well-classify-v1",
      };
    }

    if (isDrySimple(w)) {
      return { markerCategory: "dry", locationQuality: isEstimatedLocation(w) ? "estimated" : "verified", formationClass: "unknown", displayLabel: "Dry", setLabel: null, special: "dry", formation: null };
    }
    if (isBucketSimple(w)) {
      return { markerCategory: "bucket", locationQuality: isEstimatedLocation(w) ? "estimated" : "verified", formationClass: "unknown", displayLabel: "Bucket", setLabel: null, special: "bucket", formation: null };
    }

    var estimated = isEstimatedLocation(w);
    var formation = classifyFormationFromWell(w);
    var formationClass = formation.formationClass;
    var setLabel = (formation.construction && formation.construction.setLabel) || null;
    var layerStackLabel = formation.layerStackLabel || "";
    var markerCategory = estimated ? "estimated" : formationClass === "unconsolidated" ? "unconsolidated" : "rock";

    // Map face: only R@ / G chips. No Est· text. No C layer stack (detail only).
    var displayLabel;
    if (setLabel && isMapFaceSetLabel(setLabel)) displayLabel = setLabel;
    else displayLabel = "Well";

    return {
      markerCategory: markerCategory,
      locationQuality: estimated ? "estimated" : "verified",
      formationClass: formationClass,
      special: null,
      rockTopFt: formation.rockTopFt,
      unconsolidatedFt: formation.unconsolidatedFt,
      confidence: formation.confidence,
      reasons: (estimated ? ["location:estimated"] : ["location:verified"]).concat(formation.reasons),
      rulesetId: formation.rulesetId,
      displayLabel: displayLabel,
      setLabel: setLabel,
      layerStackLabel: layerStackLabel,
      formation: formation,
    };
  }

  function isUnconsolidatedWell(w) {
    return classifyWellDual(w).formationClass === "unconsolidated";
  }

  function wellTypeColor(w) {
    if (isDrySimple(w)) return "#111827";
    if (isBucketSimple(w)) return "#f97316";
    var dual = classifyWellDual(w);
    if (dual.special === "dry") return "#111827";
    if (dual.special === "bucket") return "#f97316";
    if (dual.markerCategory === "estimated" || dual.locationQuality === "estimated") return "#16a34a";
    if (dual.formationClass === "unconsolidated") return "#2563eb";
    if (dual.formationClass === "rock") return "#dc2626";
    // Clay-only / unknown: neutral slate (not fake rock red)
    return "#64748b";
  }

  function wellTypeLabel(w) {
    var dual = classifyWellDual(w);
    if (dual.special === "dry") return "Dry";
    if (dual.special === "bucket") return "Bucket";
    return dual.displayLabel;
  }

  /**
   * Parse map-face setLabel into ordered visual chip tokens.
   * Single source of truth — never invent a second R/G series (dual-label fix).
   * Tokens: r20 | g1 2 | s1 10 | g48 (legacy G@)
   */
  function parseFaceLabelTokens(label) {
    var raw = String(label || "").trim();
    if (!raw) return [];
    var parts = raw.split(/\s*[·/]\s*/);
    var other = [];
    var rock = [];
    for (var i = 0; i < parts.length; i++) {
      var p = String(parts[i] || "").trim();
      if (!p) continue;
      var r = /^R@?(\d+)$/i.exec(p);
      if (r) {
        rock.push("r" + r[1]);
        continue;
      }
      var gThick = /^G(\d+)\s+(\d+)$/i.exec(p);
      if (gThick) {
        other.push("g" + gThick[1] + " " + gThick[2]);
        continue;
      }
      var sThick = /^S(\d+)\s+(\d+)$/i.exec(p);
      if (sThick) {
        other.push("s" + sThick[1] + " " + sThick[2]);
        continue;
      }
      var gAt = /^G@(\d+)$/i.exec(p);
      if (gAt) {
        other.push("g" + gAt[1]);
        continue;
      }
    }
    // Dom 2026-07-23: rock always last (gravel before rock)
    return other.concat(rock);
  }

  /** Face-chip colors on flat combo rows: R/G white; S yellow. */
  var FACE_CHIP_COLORS = {
    r: "#ffffff",
    g: "#ffffff",
    s: "#fde047",
    sep: "rgba(255,255,255,0.75)",
  };

  function escFace(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /** HTML for R/G/S face chips on a colored combo row. Null when not a face set. */
  function formatFaceLabelHtml(label) {
    var tokens = parseFaceLabelTokens(label);
    if (!tokens.length) return null;
    var parts = [];
    for (var i = 0; i < tokens.length; i++) {
      var tok = tokens[i];
      var r = /^r(\d+)$/i.exec(tok);
      if (r) {
        parts.push(
          '<span style="color:' +
            FACE_CHIP_COLORS.r +
            ';font-weight:800">R' +
            escFace(r[1]) +
            "</span>",
        );
        continue;
      }
      var g = /^g(\d+)\s+(\d+)$/i.exec(tok);
      if (g) {
        parts.push(
          '<span style="color:' +
            FACE_CHIP_COLORS.g +
            ';font-weight:800">G' +
            escFace(g[1]) +
            " " +
            escFace(g[2]) +
            "</span>",
        );
        continue;
      }
      var s = /^s(\d+)\s+(\d+)$/i.exec(tok);
      if (s) {
        parts.push(
          '<span style="color:' +
            FACE_CHIP_COLORS.s +
            ';font-weight:800">S' +
            escFace(s[1]) +
            " " +
            escFace(s[2]) +
            "</span>",
        );
        continue;
      }
      var gBare = /^g(\d+)$/i.exec(tok);
      if (gBare) {
        parts.push(
          '<span style="color:' +
            FACE_CHIP_COLORS.g +
            ';font-weight:800">G' +
            escFace(gBare[1]) +
            "</span>",
        );
        continue;
      }
    }
    if (!parts.length) return null;
    return parts.join(
      '<span style="color:' + FACE_CHIP_COLORS.sep + ';font-weight:700"> / </span>',
    );
  }

  /**
   * Ordered list/map chip tokens from classifier setLabel only.
   * Residual gr/r only when face chips absent — prevents dual R/G.
   */
  function getOrderedTagTokens(w) {
    try {
      var dual = classifyWellDual(w);
      if (dual.special === "dry" || dual.special === "bucket") return [];
      if (dual.setLabel) {
        var fromFace = parseFaceLabelTokens(dual.setLabel);
        if (fromFace.length) return fromFace;
      }
      // Residual: rock top only, never invent dual series
      if (dual.formationClass === "rock" && dual.rockTopFt != null && dual.rockTopFt > 0) {
        return ["r" + Math.round(dual.rockTopFt)];
      }
    } catch (e) {}
    return [];
  }

  /** Plain face string for under-dot / residual map tag (setLabel preferred). */
  function wellMapFaceTag(w) {
    try {
      var dual = classifyWellDual(w);
      if (
        dual.setLabel &&
        (/^R@?\d+/i.test(dual.setLabel) ||
          /^[GS]\d+/i.test(dual.setLabel) ||
          /^G@/i.test(dual.setLabel))
      ) {
        return " " + dual.setLabel;
      }
    } catch (e2) {}
    var toks = getOrderedTagTokens(w);
    if (!toks.length) return "";
    return (
      " " +
      toks
        .map(function (t) {
          var r = /^r(\d+)$/i.exec(t);
          if (r) return "R" + r[1];
          var g = /^g(\d+)\s+(\d+)$/i.exec(t);
          if (g) return "G" + g[1] + " " + g[2];
          var s = /^s(\d+)\s+(\d+)$/i.exec(t);
          if (s) return "S" + s[1] + " " + s[2];
          var gb = /^g(\d+)$/i.exec(t);
          if (gb) return "G" + gb[1];
          return t;
        })
        .join(" / ")
    );
  }

  /** Blue gravel / red rock ring for estimated (green-fill) markers; null = white default. */
  function estimatedTypeBorderColor(w) {
    var dual = classifyWellDual(w);
    if (dual.locationQuality !== "estimated") return null;
    if (dual.formationClass === "rock") return "#dc2626";
    if (dual.formationClass === "unconsolidated") return "#2563eb";
    // Face-label fallback when formationClass unknown but R/G/S text is present
    var face = String(dual.displayLabel || dual.setLabel || "").trim();
    if (/^R\d/i.test(face) || /\bR\d/i.test(face)) return "#dc2626";
    if (/^G\d/i.test(face) || /\bG\d/i.test(face) || /^G@/i.test(face)) return "#2563eb";
    // Dry sand face → yellow ring so sand reads at a glance on green boxes
    if (/^S\d/i.test(face) || /\bS\d/i.test(face)) return "#eab308";
    return null;
  }

  function estimatedTypeRingClass(w) {
    var c = estimatedTypeBorderColor(w);
    if (c === "#dc2626") return "vj-est-rock";
    if (c === "#2563eb") return "vj-est-gravel";
    if (c === "#eab308") return "vj-est-sand";
    return "";
  }

  function estimatedTypeBorderInlineStyle(borderColor) {
    if (!borderColor) return "";
    return "border:1px solid " + borderColor + ";box-shadow:0 1px 2px rgba(0,0,0,0.35);";
  }

  /**
   * Dual-axis OR filter. estimated stays green but matches uncon/rock toggles by formation.
   * opts: { showUncon, showRock, showBucket, showDry, showEst } booleans
   */
  function passesTypeFilter(w, opts) {
    opts = opts || {};
    var showUncon = !!opts.showUncon;
    var showRock = !!opts.showRock;
    var showBucket = !!opts.showBucket;
    var showDry = !!opts.showDry;
    var showEst = !!opts.showEst;
    if (!showUncon && !showRock && !showBucket && !showDry && !showEst) return true;

    var dual = classifyWellDual(w);
    if (dual.special === "dry") return showDry;
    if (dual.special === "bucket") return showBucket;
    if (showEst && dual.locationQuality === "estimated") return true;
    if (showUncon && dual.formationClass === "unconsolidated") return true;
    if (showRock && dual.formationClass === "rock") return true;
    if (showRock && dual.locationQuality === "verified" && dual.formationClass === "unknown") return true;
    return false;
  }

  global.DnrClassifyV3 = {
    version: RULESET,
    classifyVersion: classifyVersion,
    classifyWellDual: classifyWellDual,
    classifyFormationFromWell: classifyFormationFromWell,
    isUnconsolidatedWell: isUnconsolidatedWell,
    isEstimatedLocation: isEstimatedLocation,
    wellTypeColor: wellTypeColor,
    wellTypeLabel: wellTypeLabel,
    parseFaceLabelTokens: parseFaceLabelTokens,
    formatFaceLabelHtml: formatFaceLabelHtml,
    getOrderedTagTokens: getOrderedTagTokens,
    wellMapFaceTag: wellMapFaceTag,
    estimatedTypeBorderColor: estimatedTypeBorderColor,
    estimatedTypeRingClass: estimatedTypeRingClass,
    estimatedTypeBorderInlineStyle: estimatedTypeBorderInlineStyle,
    FACE_CHIP_COLORS: FACE_CHIP_COLORS,
    passesTypeFilter: passesTypeFilter,
    formationCategoryForName: formationCategoryForName,
    analyzeConstruction: analyzeConstruction,
  };
})(typeof window !== "undefined" ? window : globalThis);
