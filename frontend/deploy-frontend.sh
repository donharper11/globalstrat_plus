#!/bin/bash
# ─── GlobalStrat Frontend Deploy ─────────────────────────────────────────
# Run from: ~/projects/globalstrat+/frontend/
#
# Usage:
#   ./deploy-frontend.sh              # Build + deploy
#   ./deploy-frontend.sh --skip-build # Deploy existing build/ without rebuilding
#   ./deploy-frontend.sh --dry-run    # Show what would happen
# ─────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ─── aide-checks deploy gate ────────────────────────────────────────────────
# Runs before anything else in this script. The pre-commit hook is a fast fail an
# agent can bypass with --no-verify; this is the layer that cannot be bypassed,
# so it is the one that decides whether work reaches production.
#
# Exit 1 = a blocking check failed. Exit 2 = a check could not run. Both refuse
# the deploy: a scanner that is absent has not passed.
#
# Set AIDE_CHECKS_SKIP=1 to bypass. That is a deliberate, visible act by a human;
# it is not something the builder does, and it is logged below.
_AIDE_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null || true)"
if [ -n "${AIDE_CHECKS_SKIP:-}" ]; then
  echo "aide-checks: BYPASSED by AIDE_CHECKS_SKIP — deploying without checks" >&2
elif [ -n "$_AIDE_ROOT" ] && [ -x "$_AIDE_ROOT/checks/bin/run-checks" ]; then
  if ! "$_AIDE_ROOT/checks/bin/run-checks" --full --repo="$_AIDE_ROOT"; then
    echo "" >&2
    echo "aide-checks: DEPLOY REFUSED — checks failed. Nothing was deployed." >&2
    exit 1
  fi
else
  echo "aide-checks: DEPLOY REFUSED — checks/bin/run-checks not found at repo root." >&2
  echo "aide-checks: a missing gate is not a passing gate." >&2
  exit 2
fi
# ─── end aide-checks deploy gate ────────────────────────────────────────────

# ─── model-routing guard ────────────────────────────────────────────────────
# Every model call must go to the LiteLLM fleet gateway through
# core/engine/llm_runner: no provider SDK, no provider endpoint, no DASHSCOPE_*
# setting. These tests read source only -- no database, no gateway, well under a
# second -- so the deploy that reaches students is also the layer that proves a
# provider call has not crept back in. Same tests run in CI on every push.
#
# Emergency override: MODEL_GUARD_OVERRIDE="<who>: <why>". A gate that can stop a
# deploy to students needs a way past it in a real emergency, or the first urgent
# deploy at a bad moment gets fixed by commenting the check out and the guard is
# gone for good. So the way past is named in the refusal itself, demands a person
# and a reason, and writes both to the deploy record below -- a deliberate,
# attributable, visible act, which editing this file is not.
MODEL_GUARD_STATUS="passed"
if [ -n "$_AIDE_ROOT" ] && [ -f "$_AIDE_ROOT/backend/manage.py" ]; then
  if ! ( cd "$_AIDE_ROOT/backend" && \
         DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-deploy-gate-not-a-real-key}" \
         DB_NAME="${DB_NAME:-unused}" DB_USER="${DB_USER:-unused}" \
         DB_PASSWORD="${DB_PASSWORD:-}" DB_HOST="${DB_HOST:-127.0.0.1}" \
         DB_PORT="${DB_PORT:-1}" \
         python3 manage.py test --noinput core.tests.test_narrative_llm_routing ); then
    # A bare or anonymous override is not an override: name yourself and say why.
    if [ -z "${MODEL_GUARD_OVERRIDE:-}" ]; then
      echo "" >&2
      echo "model-routing guard: DEPLOY REFUSED — a model call does not go through" >&2
      echo "the gateway. Nothing was deployed." >&2
      echo "" >&2
      echo "  To override in an emergency, re-run with a person and a reason:" >&2
      echo "    MODEL_GUARD_OVERRIDE=\"<your name>: <why this cannot wait>\" $0 $*" >&2
      echo "  It is recorded in the deploy record and in this run's output." >&2
      exit 1
    fi
    case "$MODEL_GUARD_OVERRIDE" in
      *:*[!\ ]*) ;;
      *)
        echo "" >&2
        echo "model-routing guard: DEPLOY REFUSED — MODEL_GUARD_OVERRIDE must read" >&2
        echo "\"<who>: <why>\", e.g. \"Dana Okafor: gateway outage, narratives already" >&2
        echo "degrade to templates\". Got: ${MODEL_GUARD_OVERRIDE}" >&2
        exit 1 ;;
    esac
    MODEL_GUARD_STATUS="OVERRIDDEN by ${MODEL_GUARD_OVERRIDE}"
    echo "" >&2
    echo "model-routing guard: OVERRIDDEN — ${MODEL_GUARD_OVERRIDE}" >&2
    echo "model-routing guard: the guard FAILED and this deploy is proceeding anyway." >&2
    echo "model-routing guard: recorded in the deploy record on the ECS host." >&2
  fi
fi
# ─── end model-routing guard ────────────────────────────────────────────────

ECS_HOST="47.86.57.36"
ECS_USER="root"
ECS_PATH="/var/www/globalstrat/build"
SSH_KEY="/home/ubuntu/.ssh/alibaba2.pem"

# Cloudflare — camdani.com zone (shared with the other apps).
[ -f "$HOME/.config/camdani/cloudflare.env" ] && . "$HOME/.config/camdani/cloudflare.env"
if [ -z "${CF_TOKEN:-}" ] || [ -z "${CF_ZONE:-}" ]; then
  echo "CF_TOKEN/CF_ZONE not set — see ~/.config/camdani/cloudflare.env" >&2
  exit 1
fi

FRONTEND_DIR="$HOME/projects/globalstrat+/frontend/globalstrat-frontend"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SKIP_BUILD=false
DRY_RUN=false

for arg in "$@"; do
  case $arg in
    --skip-build) SKIP_BUILD=true ;;
    --dry-run)    DRY_RUN=true ;;
  esac
done

log()  { echo -e "${BLUE}►${NC} $1"; }
ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
err()  { echo -e "${RED}✗${NC} $1"; exit 1; }

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  GlobalStrat Frontend Deploy${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo ""

if $DRY_RUN; then
  warn "DRY RUN — no changes will be made"
  echo ""
fi

# ── Step 1: Build ────────────────────────────────────────────────────────

if $SKIP_BUILD; then
  warn "Skipping build (--skip-build)"
  [ ! -d "$FRONTEND_DIR/build" ] && err "No build/ directory found. Run without --skip-build first."
else
  log "Building frontend..."
  if $DRY_RUN; then
    echo "   Would run: npm run build in $FRONTEND_DIR"
  else
    cd "$FRONTEND_DIR"
    npm run build 2>&1 | tail -5
    [ ! -d "build" ] && err "Build failed — no build/ directory created."
    ok "Build complete ($(find build -type f | wc -l) files, $(du -sh build | cut -f1))"
    cd - > /dev/null
  fi
fi
echo ""

# ── Step 2: Backup current files on ECS ──────────────────────────────────

BACKUP_NAME="globalstrat-backup-$(date +%Y%m%d-%H%M%S)"
log "Backing up current files on ECS..."
if $DRY_RUN; then
  echo "   Would create /var/www/$BACKUP_NAME"
else
  ssh -i "$SSH_KEY" "$ECS_USER@$ECS_HOST" \
    "if [ -d $ECS_PATH ]; then cp -r $ECS_PATH /var/www/$BACKUP_NAME; echo 'Backup: $BACKUP_NAME'; else echo 'No existing build to backup'; mkdir -p $ECS_PATH; fi"
  ok "Backup: /var/www/$BACKUP_NAME"
fi
echo ""

# ── Step 3: Deploy ───────────────────────────────────────────────────────

log "Deploying to ECS..."
if $DRY_RUN; then
  echo "   Would rsync build/ → $ECS_USER@$ECS_HOST:$ECS_PATH/"
else
  rsync -avz --delete \
    -e "ssh -i $SSH_KEY" \
    "$FRONTEND_DIR/build/" "$ECS_USER@$ECS_HOST:$ECS_PATH/" 2>&1 | tail -3
  ok "Files deployed"
fi
echo ""

# ── Step 3b: Deploy record ───────────────────────────────────────────────
# One line per deploy on the host that serves it: when, which revision, who ran
# it, which backup it can be rolled back to, and whether any gate was overridden.
# An override that lives only in someone's terminal scrollback is not recorded.

DEPLOY_RECORD="/var/www/globalstrat-deploys.log"
RECORD_LINE="$(date -u +%Y-%m-%dT%H:%M:%SZ) rev=$(git -C "$_AIDE_ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown) by=$(whoami)@$(hostname) backup=${BACKUP_NAME} model-routing-guard=${MODEL_GUARD_STATUS}"
log "Recording the deploy..."
if $DRY_RUN; then
  echo "   Would append to $ECS_USER@$ECS_HOST:$DEPLOY_RECORD"
  echo "   $RECORD_LINE"
else
  if ssh -i "$SSH_KEY" "$ECS_USER@$ECS_HOST" \
       "umask 022; printf '%s\n' \"$RECORD_LINE\" >> $DEPLOY_RECORD"; then
    ok "Deploy record: $DEPLOY_RECORD"
  else
    # Never fail a finished deploy over its own bookkeeping, but never let the
    # line disappear either.
    warn "Could not write the deploy record — record this by hand:"
    echo "   $RECORD_LINE" >&2
  fi
fi
echo ""

# ── Step 4: Verify ──────────────────────────────────────────────────────

log "Verifying..."
if $DRY_RUN; then
  echo "   Would check file count and index.html"
else
  REMOTE_COUNT=$(ssh -i "$SSH_KEY" "$ECS_USER@$ECS_HOST" "find $ECS_PATH -type f | wc -l")
  LOCAL_COUNT=$(find "$FRONTEND_DIR/build" -type f | wc -l)
  if [ "$REMOTE_COUNT" -eq "$LOCAL_COUNT" ]; then
    ok "File count matches: $LOCAL_COUNT files"
  else
    warn "File count mismatch — local: $LOCAL_COUNT, remote: $REMOTE_COUNT"
  fi

  REMOTE_SIZE=$(ssh -i "$SSH_KEY" "$ECS_USER@$ECS_HOST" "stat -c%s $ECS_PATH/index.html 2>/dev/null || echo 0")
  if [ "$REMOTE_SIZE" -gt 100 ]; then
    ok "index.html present ($REMOTE_SIZE bytes)"
  else
    err "index.html missing or empty on ECS!"
  fi
fi
echo ""

# ── Step 5: Purge Cloudflare cache ──────────────────────────────────────

log "Purging Cloudflare cache..."
if $DRY_RUN; then
  echo "   Would POST purge_cache to Cloudflare zone $CF_ZONE when CF_TOKEN is set"
elif [ -z "$CF_TOKEN" ]; then
  warn "Skipping Cloudflare purge — set CF_TOKEN in the environment to purge cache"
else
  # The files are already live by this point, so a network failure here must
  # not abort the script under `set -e`: that reported a finished deploy as
  # failed and skipped the rollback instructions (curl exit 7, 2026-09-15).
  CF_RESPONSE=$(curl -sS --retry 3 --retry-connrefused --retry-delay 5 --max-time 30 \
    -X POST \
    "https://api.cloudflare.com/client/v4/zones/${CF_ZONE}/purge_cache" \
    -H "Authorization: Bearer ${CF_TOKEN}" \
    -H "Content-Type: application/json" \
    --data '{"purge_everything":true}' 2>&1) || CF_RESPONSE="curl failed: ${CF_RESPONSE}"

  CF_SUCCESS=$(echo "$CF_RESPONSE" | grep -o '"success": *true' || true)
  if [ -n "$CF_SUCCESS" ]; then
    ok "Cloudflare cache purged"
  else
    warn "Cloudflare purge may have failed — response: $CF_RESPONSE"
  fi
fi
echo ""

# ── Done ─────────────────────────────────────────────────────────────────

echo -e "${BLUE}───────────────────────────────────────────────────${NC}"
echo ""
if [ -n "$CF_TOKEN" ]; then
  echo "  Deploy complete — cache purge requested"
else
  echo "  Deploy complete — Cloudflare cache purge skipped"
fi
echo ""
echo "  Verify: https://globalstrat.camdani.com"
echo ""
echo "  To rollback:"
echo "    ssh -i $SSH_KEY $ECS_USER@$ECS_HOST"
echo "    rm -rf $ECS_PATH && mv /var/www/$BACKUP_NAME $ECS_PATH"
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
