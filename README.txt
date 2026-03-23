C&J WELL CO — DNR Well Viewer (Portable)
========================================

FULL DNR DATASET (loads every time)
-----------------------------------
The app loads the full Indiana DNR well dataset on every page open from:  dnr_wells_full.csv

► No download button on the DNR site — use the official ArcGIS API instead. Run:  python3 fetch_dnr_wells.py  (in this folder). It fetches all wells from the state's API and writes  dnr_wells_full.csv. No scraping. See  GETTING_STARTED_FULL_DATASET.md  for details.

• Put your full well export in this folder as  dnr_wells_full.csv  (same folder as index.html). Tab- or comma-delimited; first row = headers. The app accepts latitude/longitude columns or UTM (utm_x, utm_y or easting, northing for Indiana Zone 16).

• If the file is missing or the request fails, the app falls back to a small built-in set so the map still loads.

• Vercel has a 100 MB file limit. Use the slim gzipped file: run  python3 slim_dnr_csv.py  (after fetch_dnr_wells.py). That creates  dnr_wells_slim.csv.gz  — add that to the project and deploy. The app loads  dnr_wells_slim.csv.gz  first, then  dnr_wells_slim.csv, then  dnr_wells_full.csv  if present.

HOST ON VERCEL (link that works on phone with map)
---------------------------------------------------
Deploy this folder to Vercel so you get a URL that opens in Safari with the map working. No global install needed:

1. In Terminal:  cd "/Users/dominiceasterling/DNR_Well_Viewer_Full_Demo"
2. Run:  npx vercel
3. Follow the prompts (log in with browser if asked). You'll get a URL like https://your-project.vercel.app
4. Share that link; open it in Safari on your phone — the map will load.

The folder includes index.html (a copy of the Phone viewer) so the root URL serves the map. After rebuilding the phone file, run  cp "C&J Well Viewer - Phone.html" index.html  before deploying again.

SINGLE FILE FOR PHONE (ready to send)
--------------------------------------
Send this file for phones:  C&J Well Viewer - Phone.html

Map and the 65 built-in wells work when opened from Files, email, or message. CSV drop/Export need internet; when offline use "Load Avon & Danville DNR Wells". To rebuild after editing: python3 build_from_local.py

SENDING TO ANYONE, ANYWHERE (optional, full standalone)
-----------------------------------------
So recipients can open the app from email, chat, or Files — without a server or “open in Safari”:

1. On your computer (one time), open Terminal (Mac/Linux) or Command Prompt (Windows: install Python from python.org). Go to this folder and run:
   cd "/Users/dominiceasterling/DNR_Well_Viewer_Full_Demo"
   python3 build_standalone.py
   (You need internet for this step. If you get a 403 or timeout, try another network.)

2. Send the generated file to anyone:  C&J Well Viewer - Standalone.html
   (Email, AirDrop, cloud link, etc. — one file, no zip needed.)

That file has the map and CSV libraries built in, so it works when opened from the Files app, email, or message. Map tiles still load from the internet when online.

LAUNCH ON ANY COMPUTER
----------------------
• Double-click "C&J Well Viewer.html" (or "C&J Well Viewer - Standalone.html" if you built it)
• Mac:    Or double-click "OPEN_VIEWER.command"
• Windows: Or double-click "OPEN_VIEWER.bat"

No install needed. Works offline after first load (map tiles are cached).


WHAT'S INCLUDED
--------------
• Real DNR-style wells for Avon & Danville (65 wells built in)
• Use My Location — see wells and distances from you
• Load Avon & Danville DNR Wells — loads the 65 wells and zooms the map
• Drop a CSV — drag your own well CSV onto the drop zone
• Click any well — view details and “View detailed log on this page”
• Ground elevation button — works only when the page is opened from a server (see below)


ELEVATION (OPTIONAL)
--------------------
The “Get ground elevations” button needs the page to be opened from a web server (browser security). If you want elevation:

• Mac: Double-click "START_VIEWER.command" instead. It starts a small server and opens the viewer at http://localhost:8080. Leave the Terminal window open while you use the app. Close it when done.

• Windows: Install Python from python.org, then in Command Prompt run:
    cd path\to\DNR_Well_Viewer_Full_Demo
    python -m http.server 8080
  Then open in your browser: http://localhost:8080/ and click the HTML file.


SENDING (other options)
-----------------------
• Zip the folder and send the .zip; recipients unzip and double-click the HTML file.
• Best for “anyone anywhere”: build and send the standalone file (see top of this README).

WELL LOG (Top / Bottom / Formation)
------------------------------------
The in-app table comes from **litho_parts/litho_N.json** (N = floor(refNo/10000)). Run
  python3 merge_litho_into_wells.py /path/to/litho.txt
to build those JSON files from DNR litho.txt, then deploy the whole folder (including litho_parts/).

• **Do not open the HTML as file://** if you want the Well Log table — browsers block loading the JSON. Use **START_VIEWER.command** (or `python3 -m http.server 8080`) and open **http://localhost:8080/index.html**, or deploy to Vercel.

• Demo: well **DNR-174349** ships with sample rows in **litho_parts/litho_17.json**. After starting the local server, load full DNR wells, find that well, open it — you should see the full Well Log table. Other ref numbers need you to merge full litho.txt so their shard file exists.


MOBILE
------
• Send the file (Standalone or regular); open it from the share menu in Safari or Chrome for best results.
• “Open DNR report in browser” and blue links need internet.
