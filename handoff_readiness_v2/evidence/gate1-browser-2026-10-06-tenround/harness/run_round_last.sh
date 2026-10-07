#!/usr/bin/env bash
# The tenth and last round, then the end of the game.
#
# Same shape as run_round.sh -- a playable deadline from the console first,
# four teams through every screen with team 3 in zh-CN, the blockers, the
# locks, the equity pre-flight -- but it is NOT advanced: the console offers
# *Finish game* in place of *Advance* once the open round is the scenario's
# last, and that is the control this walkthrough has to reach.
set -u
H="$(cd "$(dirname "$0")" && pwd)"
cd "$H"
ROUND=10
log() { echo "[$(date +%H:%M:%S)] r$ROUND $*" | tee -a runtime/rounds.log; }

timeout 900 python3 set_round_deadline.py "$ROUND" 24 > "runtime/deadline-r$ROUND.log" 2>&1
DRC=$?
log "deadline exit $DRC"
if [ "$DRC" -ne 0 ] || grep -q '^  FAIL' "runtime/deadline-r$ROUND.log"; then
  log "ABORT: round $ROUND has no playable deadline; not playing it"
  exit 1
fi

timeout 2400 python3 student_play.py en    1 "$ROUND" plain > "runtime/play-t1-r$ROUND.log" 2>&1 &
P1=$!
sleep 15
timeout 2400 python3 student_play.py en    2 "$ROUND" plain > "runtime/play-t2-r$ROUND.log" 2>&1 &
P2=$!
sleep 15
timeout 2400 python3 student_play.py zh-CN 3 "$ROUND" plain > "runtime/play-t3-r$ROUND.log" 2>&1 &
P3=$!
sleep 15
timeout 2400 python3 student_play.py en    4 "$ROUND" plain > "runtime/play-t4-r$ROUND.log" 2>&1 &
P4=$!
wait $P1 $P2 $P3 $P4
log "play done"

if [ -x "hooks/r$ROUND.sh" ]; then
  log "hook hooks/r$ROUND.sh starts"
  timeout 2400 "./hooks/r$ROUND.sh" > "runtime/hook-r$ROUND.log" 2>&1
  log "hook exit $?"
fi

for spec in "en 1" "en 2" "zh-CN 3" "en 4"; do
  set -- $spec
  timeout 1200 python3 follow_the_blocker.py "$1" "$2" "$ROUND" \
      > "runtime/blocker-t$2-r$ROUND.log" 2>&1
  log "blocker t$2 exit $?"
done
for spec in "en 1" "en 2" "zh-CN 3" "en 4" "en 5" "en 6"; do
  set -- $spec
  timeout 900 python3 lock_round.py "$1" "$2" "$ROUND" > "runtime/lock-t$2-r$ROUND.log" 2>&1
  log "lock t$2 exit $?"
done

SKIP=""
# A SECOND PASS, because one repair can create the next blocker. Round 2
# showed it: team 1 created a product during the round, so the Summary refused
# the lock for "Set a unit price above zero for Nova Aurora R1 in Africa."
# `follow_the_blocker` has no step for a price -- it is the affordability
# driver -- and `lock_round` is what completes the row. Completing it committed
# $300,000 of promotion against a $250,000 marketing allocation, and the
# Summary then refused THAT, in its own sentence, with nothing left to run: the
# team went to the close as a draft. A player would read the new sentence and
# do what it says, which is what `follow_the_blocker` already does -- it brings
# the declared budgets up to the spending committed -- so it is run again on
# any playing team that is not locked, and the lock is offered once more.
# Bounded to ONE extra pass on purpose: a team that still cannot lock after
# following the page twice is a finding, not something to retry away.
for spec in "en 1" "en 2" "zh-CN 3" "en 4"; do
  set -- $spec
  case " $SKIP " in
    *" $2 "*) continue ;;
  esac
  STATE="$(python3 is_locked.py "$2" "$ROUND" 2>/dev/null | tail -1)"
  log "second pass t$2: submission is $STATE"
  if [ "$STATE" != "locked" ]; then
    timeout 1200 python3 follow_the_blocker.py "$1" "$2" "$ROUND" \
        > "runtime/blocker2-t$2-r$ROUND.log" 2>&1
    log "blocker(2) t$2 exit $?"
    timeout 900 python3 lock_round.py "$1" "$2" "$ROUND" \
        > "runtime/lock2-t$2-r$ROUND.log" 2>&1
    log "lock(2) t$2 exit $? -- now $(python3 is_locked.py "$2" "$ROUND" 2>/dev/null | tail -1)"
  fi
done

python3 preflight_equity.py "$ROUND" > "runtime/preflight-r$ROUND.log" 2>&1
log "preflight exit $?"
while read -r _ ix name; do
  case "$ix" in
    3) L=zh-CN ;; *) L=en ;;
  esac
  log "preflight names $name (team $ix) -- resizing its equity"
  timeout 900 python3 fix_equity_and_lock.py "$L" "$ix" "$ROUND" \
      > "runtime/fix-equity-t$ix-r$ROUND.log" 2>&1
  log "fix equity t$ix exit $?"
done < <(grep '^REFUSE ' "runtime/preflight-r$ROUND.log" || true)

timeout 2400 python3 finish_game.py en "$ROUND" > runtime/finish-game.log 2>&1
log "finish game exit $?"
timeout 900 python3 check_round.py "$ROUND" > "runtime/check-$ROUND.log" 2>&1
log "check exit $?"
