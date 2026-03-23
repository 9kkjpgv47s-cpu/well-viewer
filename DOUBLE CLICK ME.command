#!/bin/bash
cd "$(dirname "$0")"
echo "Well Log needs this server — browser opens in 1s. Close Terminal when done."
python3 -m http.server 8080 &
sleep 1
open "http://localhost:8080/index.html"
wait
