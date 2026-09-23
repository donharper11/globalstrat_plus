#!/usr/bin/env bash
# Disposable PostgreSQL for the CE walkthrough. Never 192.168.50.38, never the
# systemd env file. Writes ./dbenv next to itself for start_stack.py / seed.py.
set -euo pipefail
S="$(cd "$(dirname "$0")" && pwd)"
CONTAINER=globalstrat-walkthrough-ce4-pg
if [ ! -s "$S/pw" ]; then openssl rand -hex 16 > "$S/pw"; chmod 600 "$S/pw"; fi
PW="$(cat "$S/pw")"
if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  docker run -d --rm --name "$CONTAINER" \
    -e POSTGRES_DB=globalstrat_walk4 -e POSTGRES_USER=walk \
    -e POSTGRES_PASSWORD="$PW" -p 127.0.0.1::5432 postgres:16-alpine >/dev/null
fi
# Readiness, walkthrough 4: `pg_isready` alone is not enough. The image's
# entrypoint runs a temporary server on the unix socket while it initialises
# the cluster, answers pg_isready there, then SHUTS IT DOWN and restarts for
# real. Walkthrough 3's loop accepted that first answer, and on this host --
# whose disk stalls -- seed.py then died with "server closed the connection
# unexpectedly". The loop now demands a real query over TCP, twice in a row.
OK=0
for _ in $(seq 1 300); do
  PORT="$(docker port "$CONTAINER" 5432/tcp | sed -n 's/.*:\([0-9][0-9]*\)$/\1/p' | head -n 1)"
  if [ -n "$PORT" ] \
     && docker exec "$CONTAINER" pg_isready -U walk >/dev/null 2>&1 \
     && docker exec -e PGPASSWORD="$PW" "$CONTAINER" \
          psql -h 127.0.0.1 -U walk -d globalstrat_walk4 -tAc 'select 1' \
          >/dev/null 2>&1; then
    OK=$((OK + 1))
    [ "$OK" -ge 2 ] && break
  else
    OK=0
  fi
  sleep 1
done
cat > "$S/dbenv" <<EOT
export DB_NAME=globalstrat_walk4
export DB_USER=walk
export DB_PASSWORD=$PW
export DB_HOST=127.0.0.1
export DB_PORT=$PORT
EOT
chmod 600 "$S/dbenv"
echo "container=$CONTAINER port=$PORT"
