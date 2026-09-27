/**
 * Optional v2 lithology classification overlay (sidecar).
 * Original lithology_json / chunks are never modified.
 *
 * Enable: ?litho_v2=1 or window.USE_LITHOLOGY_V2 = true before wells load.
 * Disable: remove query param / set USE_LITHOLOGY_V2 = false and reload.
 */
(function (global) {
    var SIDEcar_URL = 'lithology_v2/out/well_classification_v2.jsonl.gz';
    var byRef = null;
    var loadPromise = null;

    function enabled() {
        if (global.USE_LITHOLOGY_V2 === false) return false;
        if (global.USE_LITHOLOGY_V2 === true) return true;
        try {
            var q = new URLSearchParams(global.location.search || '');
            if (q.get('litho_v2') === '0') return false;
            if (q.get('litho_v2') === '1') return true;
        } catch (e) {}
        return true;
    }

    function parseJsonl(text) {
        var map = Object.create(null);
        var lines = text.split('\n');
        for (var i = 0; i < lines.length; i++) {
            var line = lines[i].trim();
            if (!line) continue;
            try {
                var rec = JSON.parse(line);
                if (rec && rec.refno) map[String(rec.refno)] = rec;
            } catch (e) { /* skip */ }
        }
        return map;
    }

    function loadSidecar() {
        if (!enabled()) return Promise.resolve(null);
        if (byRef) return Promise.resolve(byRef);
        if (loadPromise) return loadPromise;
        loadPromise = fetch(SIDEcar_URL)
            .then(function (res) {
                if (!res.ok) throw new Error('v2 sidecar HTTP ' + res.status);
                if (typeof DecompressionStream !== 'undefined' && res.body) {
                    var ds = new DecompressionStream('gzip');
                    var stream = res.body.pipeThrough(ds);
                    return new Response(stream).text();
                }
                return res.text();
            })
            .then(function (text) {
                byRef = parseJsonl(text);
                global.CJ_LITHO_V2_BY_REF = byRef;
                return byRef;
            })
            .catch(function (err) {
                console.warn('[lithology-v2] sidecar load failed — using v1 only', err);
                byRef = Object.create(null);
                return byRef;
            });
        return loadPromise;
    }

    function recordForWell(w) {
        if (!byRef || !w) return null;
        var ref = String(w.refno || w.reference_number || '').trim();
        return ref ? byRef[ref] : null;
    }

    /** Returns true=gravel/unconsolidated, false=rock/bedrock, null=use v1 */
    function wellTypeV2(w) {
        var rec = recordForWell(w);
        if (!rec) return null;
        if (rec.well_type_v2 === 'unconsolidated') return true;
        if (rec.well_type_v2 === 'bedrock') return false;
        return null;
    }

    global.CJLithologyV2 = {
        enabled: enabled,
        load: loadSidecar,
        wellType: wellTypeV2,
        recordForWell: recordForWell,
        isReady: function () { return !!byRef; }
    };

})(typeof window !== 'undefined' ? window : globalThis);
