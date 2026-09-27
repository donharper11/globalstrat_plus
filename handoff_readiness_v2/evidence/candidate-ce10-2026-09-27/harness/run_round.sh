#!/usr/bin/env bash
# Play and resolve one candidate round with four deliberately different teams.
set -euo pipefail
H="$(cd "$(dirname "$0")" && pwd)"
cd "$H"
ROUND="$1"
ILANG="$2"
log() { echo "[$(date +%H:%M:%S)] r$ROUND $*" | tee -a runtime/rounds.log; }

profile1=innovation
[ "$ROUND" -eq 1 ] && profile1=probe
declare -a pids=()
for spec in "en 1 $profile1" "en 2 scale" "zh-CN 3 resilient" "en 4 conservative"; do
  set -- $spec
  timeout 2400 python3 student_play.py "$1" "$2" "$ROUND" "$3" \
    > "runtime/play-t$2-r$ROUND.log" 2>&1 &
  pids+=("$!")
  sleep 10
done
for pid in "${pids[@]}"; do wait "$pid"; done
log "four strategy profiles played"

if [ -x "hooks/r$ROUND.sh" ]; then
  timeout 1200 "./hooks/r$ROUND.sh" > "runtime/hook-r$ROUND.log" 2>&1
  log "divergence/distress hook completed"
fi

for spec in "en 1" "en 2" "zh-CN 3" "en 4"; do
  set -- $spec
  # Complete every required product-market row first. Its promotion spend can
  # change both a category budget and total affordability, so Summary must be
  # read and corrected only after this preparation step.
  timeout 900 python3 lock_round.py "$1" "$2" "$ROUND" prepare \
    > "runtime/prepare-t$2-r$ROUND.log" 2>&1
  timeout 1200 python3 follow_the_blocker.py "$1" "$2" "$ROUND" \
    > "runtime/blocker-t$2-r$ROUND.log" 2>&1
  timeout 900 python3 lock_round.py "$1" "$2" "$ROUND" \
    > "runtime/lock-t$2-r$ROUND.log" 2>&1
done

python3 preflight_equity.py "$ROUND" > "runtime/preflight-r$ROUND.log" 2>&1
while read -r _ ix name; do
  lang=en; [ "$ix" = 3 ] && lang=zh-CN
  timeout 900 python3 fix_equity_and_lock.py "$lang" "$ix" "$ROUND" \
    > "runtime/fix-equity-t$ix-r$ROUND.log" 2>&1
  log "student-side equity correction completed for t$ix ($name)"
done < <(grep '^REFUSE ' "runtime/preflight-r$ROUND.log" || true)
python3 preflight_equity.py "$ROUND" > "runtime/preflight-post-r$ROUND.log" 2>&1
if grep -q '^REFUSE ' "runtime/preflight-post-r$ROUND.log"; then
  log "pre-close equity validation still refuses a team"
  exit 2
fi
python3 assert_round_ready.py "$ROUND"

WAIT_PROCESSED_SECONDS=300 timeout 900 python3 instructor_round.py "$ILANG" "$ROUND" console \
  > "runtime/instructor-r$ROUND.log" 2>&1
python3 check_round.py "$ROUND" > "runtime/check-r$ROUND.log" 2>&1
python3 verify_reasoning.py "$ROUND" > "runtime/reasoning-r$ROUND.log" 2>&1
python3 round_guard.py "$ROUND" "$ILANG" | tee "runtime/guard-r$ROUND.log"
log "round accepted without repair"
