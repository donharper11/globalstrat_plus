#!/usr/bin/env bash
# Run 2, replay half: the control recorded at 90b2dea, replayed at the R47 commit.
source $SCRATCH/env.sh
export DB_NAME=globalstrat_r47_control
EV="$S/evidence/run2-control"
GAME_ID="$(sed -n 's/^game_id=\([0-9]*\).*/\1/p' "$EV/fixture.log")"
cd "$WT/backend"
export GIT_REVISION="$(git rev-parse HEAD)"
echo "run2 replay: game_id=$GAME_ID tree=$WT/backend revision=$GIT_REVISION dirty=$(git status --porcelain --untracked-files=no | wc -l) start=$(date -u +%FT%TZ)"
set +e
time python3 manage.py replay_round --game-id "$GAME_ID" --round 1 \
  --restore --confirm "REPLAY-GAME-$GAME_ID-ROUND-1" --allow-source-mismatch \
  --expected-manifest "$EV/recorded/expected-manifest.json" \
  --evidence-dir "$EV/replay-at-ee94c37" \
  --label 'R47 run 2: control, recorded at 90b2dea, replayed at the R47 commit' \
  --require-env tz_env=UTC --wait-narrative 180 2>&1 | grep -v " INFO \| WARNING \| DEBUG \|Batches" | tail -n 25
echo "replay exit=${PIPESTATUS[0]}"
