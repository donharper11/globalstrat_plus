#!/usr/bin/env bash
# One round, played in Chinese, then the tour that measures the repair.
set -u
cd "$(dirname "$0")"
log() { echo "[$(date +%H:%M:%S)] $*" | tee -a runtime/redrive.log; }
log "deadline"
timeout 900 python3 set_round_deadline.py 1 24 > runtime/deadline-r1.log 2>&1; log "deadline exit $?"
log "zh student plays round 1"
timeout 2400 python3 student_play.py zh-CN 3 1 plain > runtime/play-t3-r1.log 2>&1; log "play exit $?"
timeout 1200 python3 follow_the_blocker.py zh-CN 3 1 > runtime/blocker-t3-r1.log 2>&1; log "blocker exit $?"
timeout 900 python3 lock_round.py zh-CN 3 1 > runtime/lock-t3-r1.log 2>&1; log "lock exit $?"
log "resolve"
timeout 2400 python3 instructor_round.py en 1 console > runtime/round-1.log 2>&1; log "resolve exit $?"
log "the measurement: a Chinese student's screens after resolution"
timeout 2400 python3 student_tour.py zh-CN 3 after-r1 1 > runtime/tour-t3.log 2>&1; log "zh tour exit $?"
timeout 2400 python3 student_tour.py en 1 after-r1 1 > runtime/tour-t1.log 2>&1; log "en tour exit $?"
log "done"
