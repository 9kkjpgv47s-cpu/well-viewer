#!/usr/bin/env python3
"""Patch the Well Viewer HTML: replace buildSummaryHtml, add toggle + elevation functions."""

with open("/Users/dominiceasterling/DNR_Well_Viewer_Full_Demo/C&J Well Viewer.html", "r") as f:
    content = f.read()

# 1. Replace buildSummaryHtml function
old_start = content.index("function buildSummaryHtml")
old_end = content.index("function buildFullLogHtml")
old_func = content[old_start:old_end]

new_func = r"""function buildSummaryHtml(w, dnr) {
            dnr = dnr || {};
            var logRows = wellLogRows(w, dnr);
            var rep = w.report || (w.refno ? 'https://secure.in.gov/apps/dnr/water/dnr_waterwell?refNo=' + w.refno + '&_from=SUMMARY&_action=Details' : '');
            var html = '<div class="space-y-4 text-sm">';
            if (logRows.length) {
                html += '<div class="overflow-x-auto border border-gray-200 rounded-lg" style="max-height:60vh;overflow-y:auto;"><table class="w-full text-sm border-collapse"><thead><tr class="bg-gray-100 sticky top-0 z-10"><th class="p-2 text-left border-b border-gray-200" style="width:70px">Top (ft)</th><th class="p-2 text-left border-b border-gray-200" style="width:70px">Bottom (ft)</th><th class="p-2 text-left border-b border-gray-200">Formation</th></tr></thead><tbody>';
                for (var i = 0; i < logRows.length; i++) {
                    var row = logRows[i];
                    var bg = i % 2 === 0 ? '' : ' style="background:#f9fafb"';
                    html += '<tr' + bg + '><td class="p-2 align-top font-medium">' + String(row.top != null ? row.top : '').replace(/</g, '&lt;') + '</td><td class="p-2 align-top font-medium">' + String(row.bottom != null ? row.bottom : '').replace(/</g, '&lt;') + '</td><td class="p-2 align-top">' + String(row.formation != null ? row.formation : '').replace(/</g, '&lt;') + '</td></tr>';
                }
                html += '</tbody></table></div>';
            } else {
                html += '<p class="text-gray-500 italic">No well log data on file for this well.</p>';
            }
            if (rep) {
                html += '<div style="margin-top:1rem;padding-top:0.75rem;border-top:1px solid #e5e7eb;">' +
                    '<a href="' + rep.replace(/"/g, '&quot;') + '" target="_blank" rel="noopener noreferrer" style="display:inline-flex;align-items:center;gap:0.5rem;color:#2563eb;font-weight:600;text-decoration:none;font-size:0.9rem;">' +
                    '\u{1F4C4} View Official DNR Record &amp; Well Log \u2192</a></div>';
            }
            html += '</div>';
            return html;
        }
        """

content = content.replace(old_func, new_func)

# 2. Replace showDetailById to be simpler (just show lithology + link)
old_detail_start = content.index("function showDetailById(id)")
old_detail_end = content.index("function closeModal()")
old_detail = content[old_detail_start:old_detail_end]

new_detail = r"""function showDetailById(id) {
            var w = wells.find(function(well) { return well.id === id; });
            if (!w) return;
            selectedWellForLog = w;
            document.getElementById('modalTitle').textContent = w.id + (w.loc_type ? ' \u2014 ' + w.loc_type : '');
            document.getElementById('modalContent').innerHTML = buildSummaryHtml(w, {});
            hideLogViewer();
            document.getElementById('wellModal').classList.remove('hidden');
            document.body.classList.add('modal-open');
        }

        """

content = content.replace(old_detail, new_detail)

# 3. Add toggleElevationView function + getWellBottomElev helper before the closing </script>
elev_functions = r"""
        function getWellBottomElev(w) {
            var wbe = w.well_bottom_elev;
            if (wbe != null && wbe !== '' && !isNaN(Number(wbe))) return Number(wbe);
            var ge = w.ground_elev;
            var d = w.depth;
            if (ge != null && ge !== '' && d != null && d !== '' && !isNaN(Number(ge)) && !isNaN(Number(d)) && Number(d) > 0) {
                return Math.round(Number(ge) - Number(d));
            }
            return null;
        }

        function elevColor(elev) {
            if (elev == null) return '#6b7280';
            if (elev >= 800) return '#1d4ed8';
            if (elev >= 700) return '#2563eb';
            if (elev >= 600) return '#059669';
            if (elev >= 500) return '#d97706';
            return '#dc2626';
        }

        function toggleElevationView(on) {
            elevationViewActive = on;
            addMarkersInRadius();
            updateWellsList();
        }

"""

insert_point = content.rindex("if (document.readyState")
content = content[:insert_point] + elev_functions + "        " + content[insert_point:]

# 4. Replace addMarkersInRadius to support elevation view
old_markers_start = content.index("function addMarkersInRadius()")
old_markers_end = content.index("function applyFilters()")
old_markers = content[old_markers_start:old_markers_end]

new_markers = r"""function addMarkersInRadius() {
            if (!map) return;
            clearMarkers();
            if (!searchCenter) return;
            var inRadius = getWellsWithin2Miles(searchCenter);
            inRadius.forEach(function(w) {
                var latNum = Number(w.lat);
                var lonNum = Number(w.lon);

                if (elevationViewActive) {
                    var bottomElev = getWellBottomElev(w);
                    var label = bottomElev != null ? bottomElev + "'" : '?';
                    var bgColor = elevColor(bottomElev);
                    var marker = L.marker([latNum, lonNum], {
                        icon: L.divIcon({
                            className: 'well-dot',
                            html: '<div class="elev-marker" style="background:' + bgColor + ';">' + label + '</div>',
                            iconSize: [36, 18],
                            iconAnchor: [18, 9]
                        })
                    }).bindPopup(
                        "<b>" + w.id + "</b><br>" +
                        "Bottom elev: " + (bottomElev != null ? bottomElev + " ft ASL" : "unknown") +
                        (w.depth ? "<br>Depth: " + w.depth + " ft" : "") +
                        (w.ground_elev ? "<br>Ground: " + w.ground_elev + " ft ASL" : "")
                    );
                    marker.on('click', function() { showDetailById(w.id); });
                    wellLayer.addLayer(marker);
                } else {
                    var aq = (w.aquifer || "").toLowerCase();
                    var locType = (w.location_type || w.loc_type || "").toLowerCase();
                    var isEstimated = aq.indexOf("estimated") >= 0 || locType.indexOf("estimated") >= 0;
                    var isUnconsolidated = isUnconsolidatedWell(w);
                    var bucket = isBucketWell(w);
                    var dry = isDryHole(w);
                    var color = "#dc2626";
                    if (dry) color = "#111827";
                    else if (bucket) color = "#f97316";
                    else if (isEstimated) color = "#16a34a";
                    else if (isUnconsolidated) color = "#2563eb";
                    var depthVal = (w.depth != null && w.depth !== '') ? Number(w.depth) : null;
                    var depthLabel = depthVal != null && !isNaN(depthVal) ? Math.round(depthVal).toString() : '\u2013';
                    var marker = L.marker([latNum, lonNum], {
                        icon: L.divIcon({
                            className: 'well-dot',
                            html: '<div class="well-marker" style="background:' + color + ';"><span class="well-depth-label">' + depthLabel + '</span></div>',
                            iconSize: [18, 18],
                            iconAnchor: [9, 9]
                        })
                    }).bindPopup(
                        "<b>" + w.id + "</b><br>" +
                        (depthVal != null && !isNaN(depthVal) ? depthVal : "\u2014") + " ft" +
                        "<br><a href='https://maps.apple.com/?daddr=" + latNum + "," + lonNum + "' target='_blank' rel='noopener noreferrer'>Apple Maps</a>" +
                        " \u00B7 <a href='https://www.google.com/maps/dir/?api=1&destination=" + latNum + "," + lonNum + "' target='_blank' rel='noopener noreferrer'>Google Maps</a>"
                    );
                    marker.on('click', function() { showDetailById(w.id); });
                    wellLayer.addLayer(marker);
                }
            });
        }

        """

content = content.replace(old_markers, new_markers)

# 5. Replace updateWellsList to support elevation view in list items
old_render_start = content.index("function renderRows(elevUser, elevWells)")
old_render_end = content.index("if (!listToShow.length) {\n                document.getElementById('wellsList')")
old_render = content[old_render_start:old_render_end]

new_render = r"""function renderRows(elevUser, elevWells) {
                var html = '';
                var rLon2 = referencePosFinal ? (referencePosFinal.lon != null ? referencePosFinal.lon : referencePosFinal.lng) : null;
                listToShow.forEach(function(w, i) {
                    var dist = (referencePosFinal && rLon2 != null) ? haversine(referencePosFinal.lat, rLon2, w.lat, w.lon) + ' mi' : '\u2014';
                    var safeId = String(w.id).replace(/'/g, "\\'");

                    if (elevationViewActive) {
                        var bottomElev = getWellBottomElev(w);
                        var elevText = bottomElev != null ? bottomElev + " ft ASL" : "unknown";
                        var groundText = w.ground_elev ? w.ground_elev + " ft" : "\u2014";
                        var depthText = w.depth ? w.depth + " ft" : "\u2014";
                        html += '<div onclick="showDetailById(\'' + safeId + '\')" class="card bg-gray-50 p-4 rounded-2xl cursor-pointer">' +
                            '<div class="flex justify-between items-start gap-2">' +
                            '<div class="min-w-0"><div class="font-medium truncate">' + w.id + '</div>' +
                            '<div class="text-xs text-gray-500">Ground: ' + groundText + ' \u00B7 Depth: ' + depthText + '</div>' +
                            '<div class="text-xs font-semibold" style="color:' + elevColor(bottomElev) + ';">Well bottom: ' + elevText + '</div></div>' +
                            '<div class="text-right shrink-0"><div class="font-semibold text-emerald-600">' + dist + '</div></div></div></div>';
                    } else {
                        var wellElevFt = elevWells && elevWells[i] != null ? mToFt(elevWells[i]) : null;
                        var type = isUnconsolidatedWell(w) ? 'Gravel' : 'Rock';
                        var elevLine = '';
                        if (referencePosFinal && rLon2 != null) {
                            var refLabel = gpsPosition && referencePosFinal.lat === gpsPosition.lat && referencePosFinal.lon === (gpsPosition.lon != null ? gpsPosition.lon : gpsPosition.lng) ? 'You' : 'Ref';
                            var diffText = '';
                            if (elevUser != null && wellElevFt != null) {
                                var diffFt = wellElevFt - mToFt(elevUser);
                                diffText = ' \u00B7 <strong>Diff: ' + (diffFt >= 0 ? '+' : '') + diffFt + ' ft</strong> (well \u2212 ' + refLabel.toLowerCase() + ')';
                            }
                            elevLine = '<div class="text-[10px] text-gray-600 mt-0.5">Ground elev: ' + refLabel + ' ' + (elevUser != null ? mToFt(elevUser) + ' ft' : '\u2026') + ', well ' + (wellElevFt != null ? wellElevFt + ' ft' : '\u2026') + diffText + '</div>';
                        }
                        html += '<div onclick="showDetailById(\'' + safeId + '\')" class="card bg-gray-50 p-4 rounded-2xl cursor-pointer">' +
                            '<div class="flex justify-between items-start gap-2">' +
                            '<div class="min-w-0"><div class="font-medium truncate">' + w.id + '</div><div class="text-xs text-gray-500">' + type + ' \u00B7 ' + (w.depth != null ? w.depth : '\u2014') + ' ft</div>' + elevLine + '</div>' +
                            '<div class="text-right shrink-0"><div class="font-semibold text-emerald-600">' + dist + '</div></div></div></div>';
                    }
                });
                if (!listToShow.length) {
                    html = '<p class="text-gray-500 italic">No wells within ' + RADIUS_MI + ' mi \u2014 adjust filters or try another location.</p>';
                }
                document.getElementById('wellsList').innerHTML = html;

                if (referencePosFinal && rLon2 != null && listToShow.length) {
                    var nearestDist = haversine(referencePosFinal.lat, rLon2, listToShow[0].lat, listToShow[0].lon);
                    var bannerHtml = '<strong>Wells within ' + RADIUS_MI + ' mi</strong> \u2014 <strong>Nearest:</strong> ' + nearestDist + ' mi';
                    if (elevationViewActive) {
                        var avgElev = 0, elevCount = 0;
                        listToShow.forEach(function(w) { var e = getWellBottomElev(w); if (e != null) { avgElev += e; elevCount++; } });
                        if (elevCount > 0) {
                            bannerHtml += ' \u00B7 Avg well bottom: ' + Math.round(avgElev / elevCount) + ' ft ASL (' + elevCount + ' wells)';
                        }
                    } else if (userElevationM != null) {
                        var refLabel = gpsPosition && searchCenter && searchCenter.lat === gpsPosition.lat && searchCenter.lon === (gpsPosition.lon != null ? gpsPosition.lon : gpsPosition.lng) ? 'Your ground elevation' : 'Reference elevation (search point)';
                        bannerHtml = '<strong>' + refLabel + ':</strong> ' + mToFt(userElevationM) + ' ft \u00B7 ' + bannerHtml;
                    } else {
                        bannerHtml = 'Tap <strong>Get ground elevations</strong> to compare with wells. ' + bannerHtml;
                    }
                    banner.classList.remove('hidden');
                    banner.innerHTML = bannerHtml;
                } else {
                    banner.classList.add('hidden');
                }
            }

            """

content = content.replace(old_render, new_render)

# 6. Update map center to Marion County (Indianapolis)
content = content.replace(
    "map = L.map('map', { scrollWheelZoom: false }).setView([39.7628, -86.3997], 11);",
    "map = L.map('map', { scrollWheelZoom: false }).setView([39.7684, -86.1581], 11);"
)

with open("/Users/dominiceasterling/DNR_Well_Viewer_Full_Demo/C&J Well Viewer.html", "w") as f:
    f.write(content)

print("Patch complete!")
