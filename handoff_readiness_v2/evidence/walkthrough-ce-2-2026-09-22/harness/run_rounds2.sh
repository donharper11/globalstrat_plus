#!/usr/bin/env bash
# Rounds 3 and 4 (run_rounds.sh stopped after round 2: its play() clobbered
# its own round argument with `set --`). The three teams play in parallel.
set -u
cd "$(dirname "$0")"
exec >> runtime/run_rounds.log 2>&1
set -x
play() {
  local round="$1"
  timeout 1800 python3 student_play.py en 1 "$round" plain > "runtime/play-t1-r$round.log" 2>&1 &
  sleep 20
  timeout 1800 python3 student_play.py en 2 "$round" plain > "runtime/play-t2-r$round.log" 2>&1 &
  sleep 20
  timeout 1800 python3 student_play.py zh-CN 3 "$round" plain > "runtime/play-t3-r$round.log" 2>&1 &
  wait
  echo "play r$round done"
}
resolve() {
  local round="$1" path="$2"
  timeout 1800 python3 instructor_round.py en "$round" "$path" > "runtime/round-$round.log" 2>&1
  local rc=$?
  timeout 300 python3 check_round.py "$round" > "runtime/check-$round.log" 2>&1
  echo "resolve r$round ($path) rc=$rc"
  return $rc
}
play 3
resolve 3 lifecycle || exit 1
play 4
resolve 4 console || exit 1
echo "rounds 3-4 done"
