#!/usr/bin/env bash
# Close and process a round, and recover if the engine refuses to score it.
#
#   resolve_with_recovery.sh <round> <console-lang> [way]
#
# From round 5 onwards this walkthrough found that a round every team has
# locked can still be refused at processing -- *N equity raise(s) exceed the
# funding shortfall they claim to finance* -- with nothing shown on the
# console. There is no control in the product for recovering from that, so
# this is the sequence an operator would have to work out: record the
# refusal, reopen the round, resize the named teams' raises from the Finance
# page, have everyone lock again, and close again.
#
# EVERY TIME THIS LOOP RUNS MORE THAN ONCE IS A DEFECT, and the run is
# recorded so the report can count them.
set -u
H="$(cd "$(dirname "$0")" && pwd)"
cd "$H"
ROUND="$1"; ILANG="$2"; WAY="${3:-console}"
log() { echo "[$(date +%H:%M:%S)] r$ROUND $*" | tee -a runtime/rounds.log; }

processed() {
  python3 - "$ROUND" <<'PY'
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path('.').resolve()))
from apicall import call, login
G = json.loads(pathlib.Path('game.json').read_text())
tok = login(G.get('instructor', 'walk_instructor'))
s, b = call('GET', '/api/games/%d/round-control/' % G['game_id'], token=tok)
rnd = (b or {}).get('round') or {}
want = int(sys.argv[1])
ok = (b.get('current_round', 0) > want) or (
    rnd.get('round_number') == want and rnd.get('status') == 'processed')
print('PROCESSED' if ok else 'NOT-PROCESSED')
PY
}

for attempt in 1 2 3; do
  WAIT_PROCESSED_SECONDS=90 timeout 2400 python3 instructor_round.py \
      "$ILANG" "$ROUND" "$WAY" > "runtime/round-$ROUND-try$attempt.log" 2>&1
  log "resolve attempt $attempt ($WAY, $ILANG) exit $?"
  if [ "$(processed | tail -1)" = "PROCESSED" ]; then
    log "processed on attempt $attempt"
    break
  fi
  log "THE ROUND WAS REFUSED AT PROCESSING -- attempt $attempt"
  timeout 900 python3 probe_round_wont_process.py en "$ROUND" \
      > "runtime/wont-process-r$ROUND-try$attempt.log" 2>&1
  timeout 900 python3 reopen_round.py en "$ROUND" "2026-11-0$attempt 18:00:00" \
      > "runtime/reopen-r$ROUND-try$attempt.log" 2>&1
  log "reopen exit $?"
  for spec in "en 1" "en 2" "zh-CN 3" "en 4"; do
    set -- $spec
    timeout 900 python3 fix_equity_and_lock.py "$1" "$2" "$ROUND" \
        > "runtime/fix-equity-t$2-r$ROUND-try$attempt.log" 2>&1
    log "fix equity t$2 exit $?"
  done
  for spec in "en 5" "en 6"; do
    set -- $spec
    timeout 900 python3 lock_round.py "$1" "$2" "$ROUND" \
        > "runtime/lock3-t$2-r$ROUND.log" 2>&1
  done
done
timeout 900 python3 check_round.py "$ROUND" > "runtime/check-$ROUND.log" 2>&1
log "check exit $?"
