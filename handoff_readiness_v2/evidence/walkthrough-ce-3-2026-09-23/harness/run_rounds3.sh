#!/usr/bin/env bash
# Round 3 could not be resolved through the Game Lifecycle card's Advance
# Round modal (refused: reason_required, and the modal has no reason box --
# W-CE-24). Resolve it through the round console instead, then round 4, then
# the final tours and the end-game flows.
set -u
cd "$(dirname "$0")"
exec >> runtime/run_rounds.log 2>&1
set -x
timeout 1800 python3 instructor_round.py en 3 console > runtime/round-3-console.log 2>&1 || exit 1
timeout 300 python3 check_round.py 3 > runtime/check-3.log 2>&1
timeout 1800 python3 student_play.py en 1 4 plain > runtime/play-t1-r4.log 2>&1 &
sleep 20
timeout 1800 python3 student_play.py en 2 4 plain > runtime/play-t2-r4.log 2>&1 &
sleep 20
timeout 1800 python3 student_play.py zh-CN 3 4 plain > runtime/play-t3-r4.log 2>&1 &
wait
timeout 1800 python3 instructor_round.py en 4 console > runtime/round-4.log 2>&1 || exit 1
timeout 300 python3 check_round.py 4 > runtime/check-4.log 2>&1
./run_final.sh
echo "rounds 3-4 + final done"
