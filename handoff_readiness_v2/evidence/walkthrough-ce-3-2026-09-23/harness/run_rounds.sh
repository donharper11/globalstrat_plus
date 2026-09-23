#!/usr/bin/env bash
# Rounds 2..4 end to end: resolve round 2 (Close & process now), play and
# resolve round 3 (lifecycle-card Advance Round), play and resolve round 4
# (console), cross-checking after each. Student failures do not stop the
# chain; an instructor step that fails does, so the state is left to look at.
set -u
cd "$(dirname "$0")"
log() { echo "[$(date +%H:%M:%S)] $*" >> runtime/run_rounds.log; }
play() { # round
  for spec in "en 1" "en 2" "zh-CN 3"; do
    set -- $spec
    timeout 1500 python3 student_play.py "$1" "$2" "$3" plain > "runtime/play-t$2-r$3.log" 2>&1
    log "play t$2 r$3 exit $?"
  done
}
resolve() { # round path
  timeout 1800 python3 instructor_round.py en "$1" "$2" > "runtime/round-$1.log" 2>&1
  rc=$?; log "resolve r$1 ($2) exit $rc"
  timeout 300 python3 check_round.py "$1" > "runtime/check-$1.log" 2>&1; log "check r$1 exit $?"
  return $rc
}
log "start"
resolve 2 force || exit 1
play 3
resolve 3 lifecycle || exit 1
play 4
resolve 4 console || exit 1
log "done"
