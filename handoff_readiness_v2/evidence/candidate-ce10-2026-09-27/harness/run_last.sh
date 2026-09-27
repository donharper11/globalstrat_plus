#!/usr/bin/env bash
# Play, process, and finish round 10 without reopen/force/recovery.
set -euo pipefail
H="$(cd "$(dirname "$0")" && pwd)"
cd "$H"
declare -a pids=()
for spec in "en 1 innovation" "en 2 scale" "zh-CN 3 resilient" "en 4 conservative"; do
  set -- $spec
  timeout 2400 python3 student_play.py "$1" "$2" 10 "$3" > "runtime/play-t$2-r10.log" 2>&1 &
  pids+=("$!")
  sleep 10
done
for pid in "${pids[@]}"; do wait "$pid"; done
for spec in "en 1" "en 2" "zh-CN 3" "en 4"; do
  set -- $spec
  timeout 1200 python3 follow_the_blocker.py "$1" "$2" 10 > "runtime/blocker-t$2-r10.log" 2>&1
  timeout 900 python3 lock_round.py "$1" "$2" 10 > "runtime/lock-t$2-r10.log" 2>&1
done
python3 preflight_equity.py 10 > runtime/preflight-r10.log 2>&1
while read -r _ ix name; do
  lang=en; [ "$ix" = 3 ] && lang=zh-CN
  timeout 900 python3 fix_equity_and_lock.py "$lang" "$ix" 10 > "runtime/fix-equity-t$ix-r10.log" 2>&1
done < <(grep '^REFUSE ' runtime/preflight-r10.log || true)
python3 preflight_equity.py 10 > runtime/preflight-post-r10.log 2>&1
! grep -q '^REFUSE ' runtime/preflight-post-r10.log
python3 assert_round_ready.py 10
WAIT_PROCESSED_SECONDS=300 timeout 900 python3 finish_game.py en 10 > runtime/finish-game.log 2>&1
python3 check_round.py 10 > runtime/check-r10.log 2>&1
python3 verify_reasoning.py 10 > runtime/reasoning-r10.log 2>&1

# Final browser evidence: both roles and languages, every results tab,
# reasoning UI, briefing modal, and fresh-browser language hydration.
WALK_SCREENSHOTS=1 timeout 1800 python3 student_tour.py en 1 final 10 > runtime/tour-student-en.log 2>&1
WALK_SCREENSHOTS=1 timeout 1800 python3 student_tour.py zh-CN 3 final 10 > runtime/tour-student-zh.log 2>&1
WALK_SCREENSHOTS=1 timeout 1200 python3 instructor_tour.py en final-en > runtime/tour-instructor-en.log 2>&1
WALK_SCREENSHOTS=1 timeout 1200 python3 instructor_tour.py zh-CN final-zh > runtime/tour-instructor-zh.log 2>&1
WALK_SCREENSHOTS=1 timeout 900 python3 verify_briefing.py en 1 4 > runtime/briefing-en.log 2>&1
WALK_SCREENSHOTS=1 timeout 900 python3 verify_briefing.py zh-CN 3 2 > runtime/briefing-zh.log 2>&1
WALK_SCREENSHOTS=1 timeout 900 python3 verify_fresh_browser_language.py s2609 s2609 zh-CN > runtime/fresh-student-zh.log 2>&1
WALK_SCREENSHOTS=1 timeout 900 python3 verify_fresh_browser_language.py walk_instructor candidate-ce10-pass-2026 zh-CN > runtime/fresh-instructor-zh.log 2>&1
python3 final_acceptance.py | tee runtime/final-acceptance.log
python3 records_summary.py > runtime/records-summary.log
