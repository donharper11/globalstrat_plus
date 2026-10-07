#!/usr/bin/env bash
# After round 4 is resolved: every screen once more in both languages with
# four rounds of results behind it, then the end-game flows.
set -u
cd "$(dirname "$0")"
exec >> runtime/run_final.log 2>&1
set -x
timeout 1200 python3 student_tour.py en 1 after-r4 4 > runtime/tour-t1-r4.log 2>&1 &
sleep 20
timeout 1200 python3 student_tour.py zh-CN 3 after-r4 4 > runtime/tour-t3-r4.log 2>&1 &
sleep 20
timeout 1200 python3 instructor_tour.py en en-final > runtime/tour-i-en-final.log 2>&1 &
wait
timeout 1200 python3 instructor_tour.py zh-CN zh-final > runtime/tour-i-zh-final.log 2>&1
timeout 1200 python3 instructor_endgame.py en > runtime/endgame.log 2>&1
echo "final done rc=$?"
