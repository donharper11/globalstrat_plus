#!/usr/bin/env bash
# After the last round: every screen once more in both languages, the
# read-time checks, the operator-log refusals, and the end-of-game flows.
set -u
H="$(cd "$(dirname "$0")" && pwd)"
cd "$H"
log() { echo "[$(date +%H:%M:%S)] wrapup $*" | tee -a runtime/rounds.log; }

log "start"
timeout 1800 python3 verify_ce3.py zh-CN 3 10 > runtime/ce3-t3-r10.log 2>&1
log "verify_ce3 zh exit $?"
timeout 1800 python3 verify_ce3.py en 1 10 > runtime/ce3-t1-r10.log 2>&1
log "verify_ce3 en exit $?"
timeout 1200 python3 verify_results_language.py 10 > runtime/results-language-r10.log 2>&1
log "results language exit $?"
timeout 1200 python3 probe_scorecard.py 10 1 2 4 > runtime/scorecard-r10.log 2>&1
log "scorecard exit $?"
timeout 900 python3 set_language.py student 3 zh-CN > runtime/relang-t3.log 2>&1
log "team 3 language re-asserted exit $?"
python3 probe_alert_language.py > runtime/alert-language-final.log 2>&1
log "alert language exit $?"

timeout 1800 python3 student_tour.py en 1 after-r10 10 > runtime/tour-t1-final.log 2>&1
log "student tour en exit $?"
timeout 1800 python3 student_tour.py zh-CN 3 after-r10 10 > runtime/tour-t3-final.log 2>&1
log "student tour zh exit $?"
timeout 1800 python3 instructor_tour.py en en-final > runtime/tour-i-en.log 2>&1
log "instructor tour en exit $?"
timeout 1800 python3 instructor_tour.py zh-CN zh-final > runtime/tour-i-zh.log 2>&1
log "instructor tour zh exit $?"

timeout 1200 python3 verify_operator_log_refusal.py en > runtime/oplog-en.log 2>&1
log "operator log refusals en exit $?"
timeout 1800 python3 instructor_endgame.py en > runtime/endgame.log 2>&1
log "endgame exit $?"
log "done"
