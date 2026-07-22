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

ECS_HOST="47.86.57.36"
ECS_USER="root"
ECS_PATH="/var/www/globalstrat/build"
SSH_KEY="/home/ubuntu/.ssh/alibaba2.pem"

CF_TOKEN="${CF_TOKEN:-}"
CF_ZONE="${CF_ZONE:-fafa0995894f903b99c9d9812005e487}"

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
  CF_RESPONSE=$(curl -s -X POST \
    "https://api.cloudflare.com/client/v4/zones/${CF_ZONE}/purge_cache" \
    -H "Authorization: Bearer ${CF_TOKEN}" \
    -H "Content-Type: application/json" \
    --data '{"purge_everything":true}')

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
