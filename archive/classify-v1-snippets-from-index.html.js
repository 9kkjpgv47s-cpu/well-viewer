/* FROZEN snippets from index.html — for revert reference only */

// --- isUnconsolidatedWell lines 2183-2218 ---
        function isUnconsolidatedWell(w) {
            var ov = wellGrRockOverrideKind(w);
            if (ov === 'bedrock') return false;
            if (ov === 'unconsolidated') return true;

            var aq = (w.aquifer || "").toLowerCase();
            /* Rock-like aquifers first — "sandstone"/"greensand" contain "sand" and must not classify as gravel. */
            if (/\b(bedrock|limestone|dolomite|dolostone|shale|sandstone|siltstone|greensand|granite|marble|basalt|quartzite|chert|gneiss|schist|conglomerate)\b/.test(aq)) return false;
            if (aq.indexOf("unconsolidated") >= 0 || aq.indexOf("gravel") >= 0 || aq.indexOf("sand") >= 0) return true;

            var db = parseFloat(w.depth_bedrock || "");
            var depth = parseFloat(w.depth || "");
            if (isNaN(depth) || depth <= 0) {
                var dInf = getWellDisplayDepthFt(w);
                if (dInf != null) depth = dInf;
            }
            if (!isNaN(db) && db > 0 && !isNaN(depth)) {
                if (depth > db) return false;
                return true;
            }

            var lithoRock = lithoDepthToRock(w);
            if (lithoRock != null && !isNaN(depth) && depth > lithoRock) return false;
            if (lithoRock != null && !isNaN(depth) && depth <= lithoRock) return true;

            var sd = parseFloat(w.screen_diam || w.screen_diameter || "");
            var sl = parseFloat(w.screen_length || "");
            /* Bedrock wells often have screen diameter in rock but no drift thickness in registry. */
            if (!isNaN(sd) && sd > 0) {
                var deepDiamOnly = !isNaN(depth) && depth >= 120 && (!sl || sl <= 0) && (isNaN(db) || db <= 0);
                if (!deepDiamOnly) return true;
            }
            if (!isNaN(sl) && sl > 0) return true;
            return false;
        }


// --- wellTypeColor_wellTypeLabel_passesTypeFilter lines 3138-3178 ---
        function wellTypeColor(w) {
            if (isDryHole(w)) return '#111827';
            if (isBucketWell(w)) return '#f97316';
            var aq = (w.aquifer || "").toLowerCase();
            var locType = (w.location_type || w.loc_type || "").toLowerCase();
            if (aq.indexOf("estimated") >= 0 || locType.indexOf("estimated") >= 0) return '#16a34a';
            if (isUnconsolidatedWell(w)) return '#2563eb';
            return '#dc2626';
        }

        function wellTypeLabel(w) {
            if (isDryHole(w)) return 'Dry';
            if (isBucketWell(w)) return 'Bucket';
            var aq = (w.aquifer || "").toLowerCase();
            var locType = (w.location_type || w.loc_type || "").toLowerCase();
            if (aq.indexOf("estimated") >= 0 || locType.indexOf("estimated") >= 0) return 'Est';
            if (isUnconsolidatedWell(w)) return 'Gravel';
            return 'Rock';
        }

        function passesTypeFilter(w) {
            var showUncon = document.getElementById('typeUncon') && document.getElementById('typeUncon').checked;
            var showRock = document.getElementById('typeRock') && document.getElementById('typeRock').checked;
            var showBucket = document.getElementById('typeBucket') && document.getElementById('typeBucket').checked;
            var showDry = document.getElementById('typeDry') && document.getElementById('typeDry').checked;
            var showEst = document.getElementById('typeEstimated') && document.getElementById('typeEstimated').checked;

            if (!showUncon && !showRock && !showBucket && !showDry && !showEst) return true;

            var dry = isDryHole(w);
            if (dry) return showDry;
            var bucket = isBucketWell(w);
            if (bucket) return showBucket;
            var aq = (w.aquifer || "").toLowerCase();
            var locType = (w.location_type || w.loc_type || "").toLowerCase();
            var estimated = aq.indexOf("estimated") >= 0 || locType.indexOf("estimated") >= 0;
            if (estimated) return showEst;
            var uncon = isUnconsolidatedWell(w);
            if (uncon) return showUncon;
            return showRock;
        }
