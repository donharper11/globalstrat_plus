#!/usr/bin/env bash
# The tenth and last round, then the end of the game.
#
# Round 10 is played like every other round, but it is not advanced: the
# console offers *Finish game* in place of *Advance* once the open round is
# the scenario's last, and that is the control walkthrough 3 could not reach.
set -u
H="$(cd "$(dirname "$0")" && pwd)"
cd "$H"
log() { echo "[$(date +%H:%M:%S)] r10 $*" | tee -a runtime/rounds.log; }

timeout 2400 python3 student_play.py en    1 10 plain > runtime/play-t1-r10.log 2>&1 &
P1=$!
sleep 15
timeout 2400 python3 student_play.py en    2 10 plain > runtime/play-t2-r10.log 2>&1 &
P2=$!
sleep 15
timeout 2400 python3 student_play.py zh-CN 3 10 plain > runtime/play-t3-r10.log 2>&1 &
P3=$!
sleep 15
timeout 2400 python3 student_play.py en    4 10 plain > runtime/play-t4-r10.log 2>&1 &
P4=$!
wait $P1 $P2 $P3 $P4
log "play done"

for spec in "en 1" "en 2" "zh-CN 3" "en 4"; do
  set -- $spec
  timeout 1200 python3 follow_the_blocker.py "$1" "$2" 10 \
      > "runtime/blocker-t$2-r10.log" 2>&1
  log "blocker t$2 exit $?"
done
for spec in "en 1" "en 2" "zh-CN 3" "en 4" "en 5" "en 6"; do
  set -- $spec
  timeout 900 python3 lock_round.py "$1" "$2" 10 > "runtime/lock-t$2-r10.log" 2>&1
  log "lock t$2 exit $?"
done

timeout 2400 python3 finish_game.py en 10 > runtime/finish-game.log 2>&1
log "finish game exit $?"
timeout 900 python3 check_round.py 10 > runtime/check-10.log 2>&1
log "check exit $?"
