#!/usr/bin/env python3
"""Build standalone HTML using LOCAL asset files only (no network)."""
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
INPUT_HTML = os.path.join(BASE, "C&J Well Viewer.html")
OUTPUT_HTML = os.path.join(BASE, "C&J Well Viewer - Phone.html")

ASSETS = [
    ("leaflet.js", r'<script\s+src="https://unpkg\.com/leaflet@1\.9\.4/dist/leaflet\.js"\s*></script>', "script"),
    ("leaflet.css", r'<link\s+rel="stylesheet"\s+href="https://unpkg\.com/leaflet@1\.9\.4/dist/leaflet\.css"\s*/>', "style"),
    ("MarkerCluster.css", r'<link\s+rel="stylesheet"\s+href="https://unpkg\.com/leaflet\.markercluster@1\.5\.3/dist/MarkerCluster\.css"\s*/>', "style"),
    ("MarkerCluster.Default.css", r'<link\s+rel="stylesheet"\s+href="https://unpkg\.com/leaflet\.markercluster@1\.5\.3/dist/MarkerCluster\.Default\.css"\s*/>', "style"),
    ("leaflet.markercluster.js", r'<script\s+src="https://unpkg\.com/leaflet\.markercluster@1\.5\.3/dist/leaflet\.markercluster\.js"\s*></script>', "script"),
    ("papaparse.min.js", r'<script\s+src="https://cdnjs\.cloudflare\.com/ajax/libs/PapaParse/5\.4\.1/papaparse\.min\.js"\s*></script>', "script"),
]

# Local filenames (some differ from URL)
LOCAL_FILES = {
    "leaflet.js": "leaflet.js",
    "leaflet.css": "leaflet.css",
    "MarkerCluster.css": "markercluster.css",
    "MarkerCluster.Default.css": "markercluster-default.css",
    "leaflet.markercluster.js": "markercluster.js",
    "papaparse.min.js": "papaparse.min.js",
}

def main():
    with open(INPUT_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    for key, pattern, kind in ASSETS:
        path = os.path.join(BASE, LOCAL_FILES.get(key, key))
        if not os.path.exists(path):
            print("Missing:", path)
            continue
        print("Inlining", key, "...")
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        if kind == "script":
            content = content.replace("</script>", "<\\/script>")
            replacement = "<script>\n" + content + "\n</script>"
        else:
            replacement = "<style>\n" + content + "\n</style>"
        # Use a lambda so re.sub doesn't interpret backslashes in replacement
        html = re.sub(pattern, lambda m: replacement, html, count=1)

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = os.path.getsize(OUTPUT_HTML) / 1024
    print("Wrote", OUTPUT_HTML)
    print("Size: %.1f KB — single file for phone; open from Files, email, or message." % size_kb)

if __name__ == "__main__":
    main()
