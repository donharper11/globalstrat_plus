#!/usr/bin/env bash
# One round of walkthrough 4, end to end.
#
#   run_round.sh <round> <resolve-path> <instructor-lang> [play-profile-t1]
#
# Four teams decide every round through every decision screen (team 3 in
# zh-CN); teams 5 and 6 complete and lock from the Decision Summary; teams 7
# and 8 never submit, which is the absentee path the deadline has to handle.
# Then the instructor resolves the round from the console and the round is
# cross-checked.
set -u
H="$(cd "$(dirname "$0")" && pwd)"
cd "$H"
ROUND="$1"; PATHNAME="$2"; ILANG="$3"; T1PROFILE="${4:-plain}"
log() { echo "[$(date +%H:%M:%S)] r$ROUND $*" | tee -a runtime/rounds.log; }

log "play starts"
timeout 2400 python3 student_play.py en    1 "$ROUND" "$T1PROFILE" > "runtime/play-t1-r$ROUND.log" 2>&1 &
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

# A per-round hook, if there is one: the auditor's own deliberate acts (an
# overproduction that takes a team's cash negative, an affordability probe)
# happen here, in the open round, after the teams have played and before
# anything is locked. Each hook is a file, so the record says exactly what was
# done in which round.
if [ -x "hooks/r$ROUND.sh" ]; then
  log "hook hooks/r$ROUND.sh starts"
  timeout 2400 "./hooks/r$ROUND.sh" > "runtime/hook-r$ROUND.log" 2>&1
  log "hook exit $?"
fi

# The four playing teams read the Decision Summary and do what it tells them.
# `student_play.py` commits the same budgets every round whatever the team's
# cash, which is a driver's habit and not a player's; a player who is refused
# reads the sentence and acts on it. This is that step, and it is the one the
# whole affordability question turns on.
# A team named in hooks/skip-blocker-r<N> is deliberately left with the round
# it played and no attempt to make it affordable, so that what the DEADLINE
# does with an unaffordable draft can be seen (integrator decision 14).
SKIP=""
[ -f "hooks/skip-blocker-r$ROUND" ] && SKIP="$(cat "hooks/skip-blocker-r$ROUND")"
for spec in "en 1" "en 2" "zh-CN 3" "en 4"; do
  set -- $spec
  case " $SKIP " in
    *" $2 "*) log "blocker t$2 SKIPPED on purpose (deadline test)"; continue ;;
  esac
  timeout 1200 python3 follow_the_blocker.py "$1" "$2" "$ROUND" \
      > "runtime/blocker-t$2-r$ROUND.log" 2>&1
  log "blocker t$2 exit $?"
done

# Whatever the play left unlocked -- a new product or a new market leaves a
# product-market row the lock validator asks for -- is finished the way a
# student would finish it.
for spec in "en 1" "en 2" "zh-CN 3" "en 4" "en 5" "en 6"; do
  set -- $spec
  timeout 900 python3 lock_round.py "$1" "$2" "$ROUND" > "runtime/lock-t$2-r$ROUND.log" 2>&1
  log "lock t$2 exit $?"
done

# The check the console does not have. A round in which any team's stored
# equity raise exceeds the shortfall it claims to finance cannot be scored,
# and pressing *Run post-round processing* shows the operator nothing at all
# (round 5 of this walkthrough). Any team it names is resized from the
# Finance page and locks again, and both the refusal and the repair are on
# record.
python3 preflight_equity.py "$ROUND" > "runtime/preflight-r$ROUND.log" 2>&1
log "preflight exit $?"
while read -r _ ix name; do
  case "$ix" in
    1) L=en ;; 2) L=en ;; 3) L=zh-CN ;; *) L=en ;;
  esac
  log "preflight names $name (team $ix) -- resizing its equity"
  timeout 900 python3 fix_equity_and_lock.py "$L" "$ix" "$ROUND" \
      > "runtime/fix-equity-t$ix-r$ROUND.log" 2>&1
  log "fix equity t$ix exit $?"
done < <(grep '^REFUSE ' "runtime/preflight-r$ROUND.log" || true)

./resolve_with_recovery.sh "$ROUND" "$ILANG" "$PATHNAME"
