#!/usr/bin/env python3
"""
Build a single self-contained HTML file that works for anyone, anywhere.
No CDN required — run once, then send "C&J Well Viewer - Standalone.html".
"""
import urllib.request
import re
import os
import ssl

BASE = os.path.dirname(os.path.abspath(__file__))
INPUT_HTML = os.path.join(BASE, "C&J Well Viewer.html")
OUTPUT_HTML = os.path.join(BASE, "C&J Well Viewer - Standalone.html")

# Order must match the order in the HTML file
REPLACEMENTS = [
    (r'<script\s+src="https://unpkg\.com/leaflet@1\.9\.4/dist/leaflet\.js"\s*></script>', "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js", "script"),
    (r'<link\s+rel="stylesheet"\s+href="https://unpkg\.com/leaflet@1\.9\.4/dist/leaflet\.css"\s*/>', "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css", "style"),
    (r'<link\s+rel="stylesheet"\s+href="https://unpkg\.com/leaflet\.markercluster@1\.5\.3/dist/MarkerCluster\.css"\s*/>', "https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css", "style"),
    (r'<link\s+rel="stylesheet"\s+href="https://unpkg\.com/leaflet\.markercluster@1\.5\.3/dist/MarkerCluster\.Default\.css"\s*/>', "https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css", "style"),
    (r'<script\s+src="https://unpkg\.com/leaflet\.markercluster@1\.5\.3/dist/leaflet\.markercluster\.js"\s*></script>', "https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js", "script"),
    (r'<script\s+src="https://cdnjs\.cloudflare\.com/ajax/libs/PapaParse/5\.4\.1/papaparse\.min\.js"\s*></script>', "https://cdnjs.cloudflare.com/ajax/libs/PapaParse/5.4.1/papaparse.min.js", "script"),
]

def download(url):
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0"})
    with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")

def main():
    with open(INPUT_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    for pattern, url, kind in REPLACEMENTS:
        print("Fetching", url.split("/")[-1], "...")
        content = download(url)
        if kind == "script":
            content = content.replace("</script>", "<\\/script>")
            replacement = "<script>\n" + content + "\n</script>"
        else:
            replacement = "<style>\n" + content + "\n</style>"
        html = re.sub(pattern, replacement, html, count=1)

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = os.path.getsize(OUTPUT_HTML) / 1024
    print("Wrote", OUTPUT_HTML)
    print("Size: %.1f KB — send this single file to anyone; it works offline and from any device." % size_kb)

if __name__ == "__main__":
    main()
