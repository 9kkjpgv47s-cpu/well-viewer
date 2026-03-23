Place DNR WellLogs exports here (surrounding counties + Marion).

Accepted:
  • *.csv  — comma-separated, header row with RefNum (or RefNo), From/To or Top/Bottom, Formation
  • *.txt  — often tab-separated; same columns

After adding files, rebuild statewide chunks on YOUR Mac (not Vercel):

  cd ~/DNR_Well_Viewer_Full_Demo
  python3 build_statewide_data.py

Optional: point to explicit files (macOS uses : between paths):

  export DNR_LOGS_CSV_PATHS="$HOME/Downloads/WellLogs_A.csv:$HOME/Downloads/WellLogs_B.csv"
  python3 build_statewide_data.py

Raw logs are NOT uploaded by Vercel (.vercelignore blocks *.csv/*.txt). Only the
generated statewide_wells_chunk_*.csv.gz files are deployed with the site.
