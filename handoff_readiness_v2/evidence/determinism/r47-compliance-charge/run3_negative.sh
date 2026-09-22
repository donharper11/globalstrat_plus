#!/usr/bin/env bash
# Run 3 (negative smoke): the CHARGED round from run 1, recorded at the R47
# commit, replayed at the BASE tree. Expected: competitive hash differs
# (exit 3) -- the base engine charges nothing, so the lever is provably
# inside the envelope and the change is byte-identical only when unused.
source $SCRATCH/env.sh
export DB_NAME=globalstrat_r47
EV="$S/evidence/run3-negative-charged-at-base"
mkdir -p "$EV"
GAME_ID="$(sed -n 's/^game_id=\([0-9]*\).*/\1/p' "$S/evidence/run1-charged/fixture.log")"
cd "$S/base/backend"
export GIT_REVISION=90b2deaf6d603f384941c29b9ecadc46bcb415d1
echo "run3: game_id=$GAME_ID tree=$S/base/backend revision=$GIT_REVISION start=$(date -u +%FT%TZ)"
set +e
time python3 manage.py replay_round --game-id "$GAME_ID" --round 1 \
  --restore --confirm "REPLAY-GAME-$GAME_ID-ROUND-1" --allow-source-mismatch \
  --expected-manifest "$S/evidence/run1-charged/recorded/expected-manifest.json" \
  --evidence-dir "$EV" \
  --label 'R47 run 3: charged round recorded at the R47 commit, replayed at 90b2dea' \
  --require-env tz_env=UTC --wait-narrative 180 2>&1 | grep -v " INFO \| WARNING \| DEBUG \|Batches" | tail -n 40
echo "replay exit=${PIPESTATUS[0]}"
