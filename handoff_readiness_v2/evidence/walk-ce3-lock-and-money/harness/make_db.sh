#!/usr/bin/env bash
# Disposable PostgreSQL for the WALK-CE3 lock-and-money whole-game proof.
# Never 192.168.50.38, never the systemd env file. Its own container, its own
# ephemeral host port, its own database; another builder's runner is untouched.
set -euo pipefail
S="$(cd "$(dirname "$0")" && pwd)"
CONTAINER=globalstrat-walk-ce3-lockmoney-pg
if [ ! -s "$S/pw" ]; then openssl rand -hex 16 > "$S/pw"; chmod 600 "$S/pw"; fi
PW="$(cat "$S/pw")"
if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  docker run -d --rm --name "$CONTAINER" \
    -e POSTGRES_DB=globalstrat_walkce3lm -e POSTGRES_USER=walk \
    -e POSTGRES_PASSWORD="$PW" -p 127.0.0.1::5432 postgres:16-alpine >/dev/null
fi
for _ in $(seq 1 600); do
  PORT="$(docker port "$CONTAINER" 5432/tcp | sed -n 's/.*:\([0-9][0-9]*\)$/\1/p' | head -n 1)"
  if [ -n "$PORT" ] && docker exec "$CONTAINER" pg_isready -U walk >/dev/null 2>&1; then break; fi
  sleep 1
done
cat > "$S/dbenv" <<EOT
export DB_NAME=globalstrat_walkce3lm
export DB_USER=walk
export DB_PASSWORD=$PW
export DB_HOST=127.0.0.1
export DB_PORT=$PORT
EOT
chmod 600 "$S/dbenv"
echo "container=$CONTAINER port=$PORT"
