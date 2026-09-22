#!/usr/bin/env bash
# Run 2 (control): at the BASE commit 90b2dea, a round with NO compliance
# investment, recorded there; then replayed at the R47 commit from the base
# run's pre-resolution backup, with --allow-source-mismatch because the two
# source trees differ by construction.
source $SCRATCH/env.sh
export DB_NAME=globalstrat_r47_control
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS $DB_NAME;" -c "CREATE DATABASE $DB_NAME;" >/dev/null
EV="$S/evidence/run2-control"
mkdir -p "$EV"

# --- record at base -------------------------------------------------------
cd "$S/base/backend"
export GIT_REVISION=90b2deaf6d603f384941c29b9ecadc46bcb415d1
echo "run2 record: tree=$S/base/backend revision=$GIT_REVISION start=$(date -u +%FT%TZ)"
python3 manage.py migrate --noinput -v 0
python3 manage.py load_scenario --preset electronics > "$EV/load_scenario.log" 2>&1
tail -n 1 "$EV/load_scenario.log"
time python3 ../handoff_readiness_v2/determinism_fixture.py --teams 4 --rounds 1 \
  --name R47-CONTROL --section-id 90048 --no-compliance-investment \
  2>&1 | grep -v " INFO \| WARNING \| DEBUG \|Batches" | tee "$EV/fixture.log"
GAME_ID="$(sed -n 's/^game_id=\([0-9]*\).*/\1/p' "$EV/fixture.log")"
echo "game_id=$GAME_ID"
python3 manage.py replay_round --game-id "$GAME_ID" --round 1 --export-only \
  --evidence-dir "$EV/recorded" 2>&1 | grep -v " INFO \| WARNING \| DEBUG " | tail -n 3
python3 manage.py replay_round --game-id "$GAME_ID" --round 1 --verify-only \
  --expected-manifest "$EV/recorded/expected-manifest.json" \
  --evidence-dir "$EV/verify-at-base" 2>&1 | grep -v " INFO \| WARNING \| DEBUG " | tail -n 3

# --- replay at the R47 commit --------------------------------------------
cd "$WT/backend"
export GIT_REVISION="$(git rev-parse HEAD)"
echo "run2 replay: tree=$WT/backend revision=$GIT_REVISION dirty=$(git status --porcelain --untracked-files=no | wc -l) start=$(date -u +%FT%TZ)"
time python3 manage.py replay_round --game-id "$GAME_ID" --round 1 \
  --restore --confirm "REPLAY-GAME-$GAME_ID-ROUND-1" --allow-source-mismatch \
  --expected-manifest "$EV/recorded/expected-manifest.json" \
  --evidence-dir "$EV/replay-at-r47" \
  --label 'R47 run 2: control, recorded at 90b2dea, replayed at the R47 commit' \
  --require-env tz_env=UTC --wait-narrative 180 2>&1 | grep -v " INFO \| WARNING \| DEBUG \|Batches" | tail -n 25
echo "replay exit=${PIPESTATUS[0]}"
