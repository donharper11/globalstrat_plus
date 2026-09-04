#!/usr/bin/env bash
# V2-048 — rotate the shared PostgreSQL role `donwh`.
#
# Run as:  sudo bash ops/rotate-db-credential.sh
#
# Needs root: /etc/globalstrat-plus.env is root:root 0600 and the services are
# systemd-managed. Everything else is prepared and already committed.
#
# THE SECRET IS NEVER PRINTED. Not on success, not on failure, not in the
# rollback path. Digest prefixes are shown so two values can be compared
# without either being disclosed.
#
# One role, three applications, two repositories:
#   globalstrat+   /etc/globalstrat-plus.env          (systemd, root 0600)
#   globalstrat v1 ~/.globalstrat-secrets.env         (cron, ubuntu 0600)
#   BECSR          ~/projects/BECSR/.becsr-secrets.env (systemd, ubuntu 0600)
# Rotating without all three stops the other two -- and not at rotation:
# existing pooled connections keep working, so they fail later, at reconnect.
# That was measured, not assumed; see the drill evidence.
set -uo pipefail

HOST=192.168.50.38
ROLE=donwh
OWNER_HOME=/home/ubuntu
GS_ENV=/etc/globalstrat-plus.env
V1_ENV="$OWNER_HOME/.globalstrat-secrets.env"
BECSR_ENV="$OWNER_HOME/projects/BECSR/.becsr-secrets.env"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$OWNER_HOME/v2-048-rotation-$STAMP.log"

[ "$(id -u)" -eq 0 ] || { echo "must run as root (sudo bash $0)"; exit 2; }

say()  { echo "$*" | tee -a "$LOG"; }
dig()  { printf '%s' "$1" | sha256sum | cut -c1-12; }

fail_and_rollback() {
  say ""
  say "FAILED: $1"
  say "ROLLING BACK ..."
  psql -h "$HOST" -U "$ROLE" -d postgres -q \
       -c "ALTER ROLE $ROLE PASSWORD '$OLD';" >/dev/null 2>&1 \
    && say "  role password restored" || say "  ROLE RESTORE FAILED — MANUAL ACTION REQUIRED"
  for f in "$GS_ENV" "$V1_ENV" "$BECSR_ENV"; do
    [ -f "$f.pre-$STAMP" ] && { cp -p "$f.pre-$STAMP" "$f"; say "  restored $f"; }
  done
  systemctl restart globalstrat-backend.service 2>/dev/null && say "  globalstrat-backend restarted"
  systemctl restart becsr-backend.service       2>/dev/null && say "  becsr-backend restarted"
  say ""
  say "Rolled back to the pre-rotation credential. Log: $LOG"
  exit 1
}

say "V2-048 credential rotation — $STAMP"
say ""

# ── 0. the current credential, read from the running service ───────────────
PID="$(systemctl show -p MainPID --value globalstrat-backend.service)"
OLD="$(tr '\0' '\n' < "/proc/$PID/environ" | sed -n 's/^DB_PASSWORD=//p')"
[ -n "$OLD" ] || { echo "cannot read the current credential from PID $PID"; exit 2; }
say "current credential digest : $(dig "$OLD")"

export PGPASSWORD="$OLD"
psql -h "$HOST" -U "$ROLE" -d postgres -tAc 'select 1' >/dev/null 2>&1 \
  || { echo "the current credential does not authenticate; aborting before any change"; exit 2; }
say "preflight                 : current credential authenticates"

# ── 1. generate the replacement ────────────────────────────────────────────
NEW="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
say "replacement digest        : $(dig "$NEW")  (32 bytes, urlsafe)"

# ── 2. back up every config we are about to touch ──────────────────────────
for f in "$GS_ENV" "$V1_ENV" "$BECSR_ENV"; do
  [ -f "$f" ] && { cp -p "$f" "$f.pre-$STAMP"; chmod 600 "$f.pre-$STAMP"; say "backed up                 : $f -> $f.pre-$STAMP"; }
done

# ── 3. rotate the role ─────────────────────────────────────────────────────
psql -h "$HOST" -U "$ROLE" -d postgres -v ON_ERROR_STOP=1 -q \
     -c "ALTER ROLE $ROLE PASSWORD '$NEW';" >/dev/null 2>&1 \
  || fail_and_rollback "ALTER ROLE did not succeed"
say "rotated                   : ALTER ROLE $ROLE PASSWORD"

# ── 4. update every consumer ───────────────────────────────────────────────
upd() {  # file, key
  local f="$1" k="$2"
  [ -f "$f" ] || { say "  (absent, skipped) $f"; return 0; }
  if grep -q "^$k=" "$f"; then
    python3 - "$f" "$k" "$NEW" <<'PY'
import pathlib, sys
path, key, val = sys.argv[1], sys.argv[2], sys.argv[3]
p = pathlib.Path(path)
out = [f'{key}={val}' if l.startswith(f'{key}=') else l
       for l in p.read_text().splitlines()]
p.write_text('\n'.join(out) + '\n')
PY
  else
    printf '%s=%s\n' "$k" "$NEW" >> "$f"
  fi
  chmod 600 "$f"; say "  updated $k in $f"
}
upd "$GS_ENV"    DB_PASSWORD
upd "$V1_ENV"    DB_PASSWORD
upd "$BECSR_ENV" BECSR_DB_PASSWORD
chown ubuntu:ubuntu "$V1_ENV" "$BECSR_ENV" 2>/dev/null

# ── 5. restart the consumers that hold connections ─────────────────────────
# Measured: ALTER ROLE does not disconnect live sessions, so a service that is
# not restarted keeps serving and fails later, at its next reconnect.
systemctl restart globalstrat-backend.service || fail_and_rollback "globalstrat-backend did not restart"
systemctl restart becsr-backend.service       || fail_and_rollback "becsr-backend did not restart"
sleep 5
say "restarted                 : globalstrat-backend, becsr-backend"

# ── 6. verify ──────────────────────────────────────────────────────────────
PGPASSWORD="$NEW" psql -h "$HOST" -U "$ROLE" -d postgres -tAc 'select 1' >/dev/null 2>&1 \
  || fail_and_rollback "the new credential does not authenticate"
say "verified                  : new credential authenticates"

if PGPASSWORD="$OLD" psql -h "$HOST" -U "$ROLE" -d postgres -tAc 'select 1' >/dev/null 2>&1; then
  fail_and_rollback "the OLD credential is still accepted"
fi
say "verified                  : old credential REFUSED"

systemctl is-active --quiet globalstrat-backend.service || fail_and_rollback "globalstrat-backend is not active"
systemctl is-active --quiet becsr-backend.service       || fail_and_rollback "becsr-backend is not active"
say "verified                  : both services active"

sudo -u ubuntu env -i HOME="$OWNER_HOME" PATH=/usr/bin:/bin \
  bash -lc "cd $OWNER_HOME/projects/globalstrat/backend && python3 manage.py check_round_deadlines" \
  >/dev/null 2>&1 \
  && say "verified                  : globalstrat v1 cron authenticates" \
  || fail_and_rollback "the globalstrat v1 deadline cron cannot authenticate"

say ""
say "ROTATION COMPLETE."
say "  role            : $ROLE @ $HOST"
say "  new digest      : $(dig "$NEW")"
say "  old digest      : $(dig "$OLD")  (refused)"
say "  backups         : *.pre-$STAMP  (delete once you are satisfied)"
say "  log             : $LOG"
say ""
say "Still outstanding for V2-048: the value remains in 14 commits of git"
say "history behind a GitHub remote. Rotation makes that history harmless;"
say "rewriting it is a separate decision."
