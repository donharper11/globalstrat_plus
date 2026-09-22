#!/usr/bin/env bash
# Run 1: at the R47 commit, a round WITH compliance investment, recorded and
# then replayed at the same commit from its pre-resolution backup.
source $SCRATCH/env.sh
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS $DB_NAME;" -c "CREATE DATABASE $DB_NAME;" >/dev/null
cd "$WT/backend"
export GIT_REVISION="$(git rev-parse HEAD)"
echo "run1 revision=$GIT_REVISION dirty=$(git status --porcelain --untracked-files=no | wc -l) start=$(date -u +%FT%TZ)"
EV="$S/evidence/run1-charged-ee94c37"
mkdir -p "$EV"

python3 manage.py migrate --noinput -v 0
python3 manage.py load_scenario --preset electronics > "$EV/load_scenario.log" 2>&1
tail -n 2 "$EV/load_scenario.log"

time python3 ../handoff_readiness_v2/determinism_fixture.py --teams 4 --rounds 1 \
  --name R47-CHARGED-B --section-id 90047 2>&1 | grep -v " INFO \| WARNING " | tee "$EV/fixture.log"
GAME_ID="$(sed -n 's/^game_id=\([0-9]*\).*/\1/p' "$EV/fixture.log")"
echo "game_id=$GAME_ID"

python3 manage.py replay_round --game-id "$GAME_ID" --round 1 --export-only \
  --evidence-dir "$EV/recorded" 2>&1 | grep -v " INFO \| WARNING " | tail -n 5

time python3 manage.py replay_round --game-id "$GAME_ID" --round 1 \
  --restore --confirm "REPLAY-GAME-$GAME_ID-ROUND-1" \
  --expected-manifest "$EV/recorded/expected-manifest.json" \
  --evidence-dir "$EV/replay" --label 'R47 run 1: charged round, same commit' \
  --require-env tz_env=UTC --wait-narrative 180 2>&1 | grep -v " INFO \| WARNING " | tail -n 25
echo "replay exit=${PIPESTATUS[0]}"
