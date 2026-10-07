#!/usr/bin/env bash
# Round 5 had to be reopened: it closed with every team locked and then
# refused to process, because two teams had locked an equity raise the engine
# rejects. Teams 3 and 4 have been resized and have locked again; the reopen
# put every other team back to draft, so they lock again here. Then the round
# is closed and processed, the pre-flight the console does not have is run
# first, and the game goes on to round 9.
set -u
H="$(cd "$(dirname "$0")" && pwd)"
cd "$H"
log() { echo "[$(date +%H:%M:%S)] r5 $*" | tee -a runtime/rounds.log; }
for spec in "en 1" "en 2"; do
  set -- $spec
  timeout 1200 python3 follow_the_blocker.py "$1" "$2" 5 \
      > "runtime/blocker2-t$2-r5.log" 2>&1
  log "blocker(2) t$2 exit $?"
done
for spec in "en 1" "en 2" "zh-CN 3" "en 4" "en 5" "en 6"; do
  set -- $spec
  timeout 900 python3 lock_round.py "$1" "$2" 5 > "runtime/lock2-t$2-r5.log" 2>&1
  log "lock(2) t$2 exit $?"
done
python3 preflight_equity.py 5 > runtime/preflight-r5.log 2>&1
log "preflight exit $?"
timeout 2400 python3 instructor_round.py zh-CN 5 console > runtime/round-5b.log 2>&1
log "resolve (console, zh-CN) exit $?"
timeout 900 python3 check_round.py 5 > runtime/check-5.log 2>&1
log "check exit $?"
./run_game.sh 6 9
./run_last.sh
