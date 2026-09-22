#!/usr/bin/env bash
# Disposable replay stack for the R47 determinism evidence. Sourced by the
# step scripts. Never touches 192.168.50.38 and never reads the systemd env.
set -euo pipefail
S=$SCRATCH
WT=$REPO
CONTAINER=globalstrat-r47-replay-pg

if [ ! -s "$S/pw" ]; then
  openssl rand -hex 16 > "$S/pw"; chmod 600 "$S/pw"
fi
export DB_NAME=globalstrat_r47
export DB_USER=r47
export DB_PASSWORD="$(cat "$S/pw")"
export DB_HOST=127.0.0.1

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  docker run -d --rm --name "$CONTAINER" \
    -e POSTGRES_DB="$DB_NAME" -e POSTGRES_USER="$DB_USER" \
    -e POSTGRES_PASSWORD="$DB_PASSWORD" \
    -p 127.0.0.1::5432 postgres:16-alpine >/dev/null
fi
for _ in $(seq 1 30); do
  DB_PORT="$(docker port "$CONTAINER" 5432/tcp | sed -n 's/.*:\([0-9][0-9]*\)$/\1/p' | head -n 1)"
  if [ -n "$DB_PORT" ] && pg_isready -h 127.0.0.1 -p "$DB_PORT" -U "$DB_USER" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
export DB_PORT

export DJANGO_SETTINGS_MODULE=globalstrat.settings
export COMPETITION_BACKUP_DIR="$S/backups"
export COMPETITION_RECOVERY_ENABLED=true
# Phase 2 must not reach a real model: an unreachable endpoint, as run C did.
export LLM_GATEWAY_URL=http://127.0.0.1:9/v1/chat/completions
export DASHSCOPE_COMPATIBLE_URL=http://127.0.0.1:9/v1/chat/completions
export DASHSCOPE_MODEL=unreachable-endpoint
export NARRATIVE_LLM_URL=http://127.0.0.1:9/v1/chat/completions

echo "stack: container=$CONTAINER db=$DB_NAME host=$DB_HOST port=$DB_PORT backups=$COMPETITION_BACKUP_DIR pid=$$"
