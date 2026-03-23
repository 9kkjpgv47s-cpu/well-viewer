#!/bin/bash
cd /Users/dominiceasterling/DNR_Well_Viewer_Full_Demo
pairs=(
" WellRecords_84695122.csv WellLogs_42894351.csv "
" WellRecords_02403779.csv WellLogs_24205733.csv "
" WellRecords_69345115.csv WellLogs_43510722.csv "
" WellRecords_74449641.csv WellLogs_20709648.csv "
" WellRecords_83637591.csv WellLogs_42915275.csv "
" WellRecords_58980702.csv WellLogs_32667032.csv "
" WellRecords_50145762.csv WellLogs_54216464.csv "
" WellRecords_18401673.csv WellLogs_82531062.csv "
" WellRecords_78993669.csv WellLogs_21726418.csv "
)
for pair in "${pairs[@]}"; do
  set -- $pair
  python3 build_other_counties.py /Users/dominiceasterling/Downloads/$1 /Users/dominiceasterling/Downloads/$2
done
