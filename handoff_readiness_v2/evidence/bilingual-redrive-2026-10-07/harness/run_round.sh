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

# THE FIXTURE OPENS ROUNDS WHOSE DEADLINE HAS ALREADY PASSED. The schedule
# instructor_setup.py generates starts at a fixed 2026-09-22, so every round
# after the first opens already expired and the product correctly refuses
# every write; rounds 2 and 3 of the 2026-10-06 candidate run produced 183
# failed steps for that reason alone, against zero in round 1. So the round
# is given a playable deadline FIRST, through the console's own controls
# rather than a database edit, and -- unlike the earlier run -- a deadline
# step that fails STOPS the round instead of being logged and ignored.
#
# A round named in hooks/extend-deadline-r<N> is first driven through *Extend
# Deadline* on its expired deadline, which is the route branch that gives the
# full extension from `now` rather than from a spent window. Every round then
# gets a deliberate absolute deadline from the *Set deadline* control.
if [ -f "hooks/extend-deadline-r$ROUND" ]; then
  timeout 900 python3 extend_deadline.py "$ROUND" 24 "$ILANG" \
      > "runtime/extend-r$ROUND.log" 2>&1
  XRC=$?
  log "extend deadline exit $XRC"
  # The driver writes its record and exits 0 whatever it found, so the exit
  # code alone would accept a round it never touched. A failed STEP stops the
  # round, for the same reason the deadline step below does.
  if [ "$XRC" -ne 0 ] || grep -q '^  FAIL' "runtime/extend-r$ROUND.log"; then
    log "ABORT: Extend Deadline failed on round $ROUND"
    exit 1
  fi
fi

timeout 900 python3 set_round_deadline.py "$ROUND" 24 > "runtime/deadline-r$ROUND.log" 2>&1
DRC=$?
log "deadline exit $DRC"
if [ "$DRC" -ne 0 ]; then
  log "ABORT: round $ROUND has no playable deadline; not playing it"
  exit 1
fi
if grep -q '^  FAIL' "runtime/deadline-r$ROUND.log"; then
  log "ABORT: the deadline driver reported a failed step on round $ROUND"
  exit 1
fi

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
    1) L=en ;; 2) L=en ;; 3) L=zh-CN ;; *) L=en ;;
  esac
  log "preflight names $name (team $ix) -- resizing its equity"
  timeout 900 python3 fix_equity_and_lock.py "$L" "$ix" "$ROUND" \
      > "runtime/fix-equity-t$ix-r$ROUND.log" 2>&1
  log "fix equity t$ix exit $?"
done < <(grep '^REFUSE ' "runtime/preflight-r$ROUND.log" || true)

./resolve_with_recovery.sh "$ROUND" "$ILANG" "$PATHNAME"
