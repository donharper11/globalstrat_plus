#!/usr/bin/env bash
# The whole ten-round game, with every round given a playable deadline from
# the console first. instructor_setup.py must already have run (it builds the
# course, section, game, roster and team assignment and writes game.json).
set -u
H="$(cd "$(dirname "$0")" && pwd)"
cd "$H"
log() { echo "[$(date +%H:%M:%S)] tenround $*" | tee -a runtime/rounds.log; }
log "rounds 1-9 start"
./run_game.sh 1 9
log "rounds 1-9 exit $?"
./run_round_last.sh
log "round 10 exit $?"
./run_wrapup.sh
log "wrapup exit $?"
log "done"
