#!/usr/bin/env bash
# Round 4 was interrupted so that the affordability dead end could be driven
# by hand (all four playing teams have since locked it themselves). This
# finishes round 4 from where it stopped and then runs rounds 5 to 9.
set -u
H="$(cd "$(dirname "$0")" && pwd)"
cd "$H"
log() { echo "[$(date +%H:%M:%S)] r4 $*" | tee -a runtime/rounds.log; }
for t in 5 6; do
  timeout 900 python3 lock_round.py en "$t" 4 > "runtime/lock-t$t-r4.log" 2>&1
  log "lock t$t exit $?"
done
timeout 2400 python3 instructor_round.py zh-CN 4 force > runtime/round-4.log 2>&1
log "resolve (force, zh-CN) exit $?"
timeout 900 python3 check_round.py 4 > runtime/check-4.log 2>&1
log "check exit $?"
./run_game.sh 5 9
