#!/bin/bash
# ─── GlobalStrat Production Setup ────────────────────────────────────────
# Run with: sudo bash setup-services.sh
# Installs systemd services for the backend and FRP tunnel.
# ─────────────────────────────────────────────────────────────────────────

set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== GlobalStrat — Installing production services ==="
echo ""

# 1. FRP client config
echo "[1/4] Installing FRP client config..."
mkdir -p /etc/frp
cp "$DEPLOY_DIR/frpc.toml" /etc/frp/frpc-globalstrat.toml
echo "  → /etc/frp/frpc-globalstrat.toml"

# 2. Systemd services
echo "[2/4] Installing systemd services..."
cp "$DEPLOY_DIR/globalstrat-backend.service" /etc/systemd/system/
cp "$DEPLOY_DIR/globalstrat-frpc.service" /etc/systemd/system/
systemctl daemon-reload
echo "  → globalstrat-backend.service"
echo "  → globalstrat-frpc.service"

# 3. Enable and start services
echo "[3/4] Enabling and starting services..."

# Stop any existing dev server on port 8002
EXISTING_PID=$(ss -tlnp | grep ':8002' | grep -oP 'pid=\K\d+' || true)
if [ -n "$EXISTING_PID" ]; then
  echo "  Stopping existing process on port 8002 (PID $EXISTING_PID)..."
  kill "$EXISTING_PID" 2>/dev/null || true
  sleep 2
fi

systemctl enable --now globalstrat-backend.service
systemctl enable --now globalstrat-frpc.service
echo "  → Both services enabled and started"

# 4. Verify
echo "[4/4] Verifying..."
sleep 3

BACKEND_STATUS=$(systemctl is-active globalstrat-backend.service)
FRP_STATUS=$(systemctl is-active globalstrat-frpc.service)

echo "  Backend: $BACKEND_STATUS"
echo "  FRP:     $FRP_STATUS"

if [ "$BACKEND_STATUS" = "active" ] && [ "$FRP_STATUS" = "active" ]; then
  echo ""
  echo "=== All services running ==="
  echo ""
  echo "  Backend:  http://127.0.0.1:8002/api/"
  echo "  FRP:      localhost:8002 → ECS:3006"
  echo "  Frontend: https://globalstrat.camdani.com"
  echo ""
  echo "  Logs:"
  echo "    journalctl -u globalstrat-backend -f"
  echo "    journalctl -u globalstrat-frpc -f"
else
  echo ""
  echo "!!! Some services failed to start. Check logs:"
  echo "  journalctl -u globalstrat-backend --no-pager -n 20"
  echo "  journalctl -u globalstrat-frpc --no-pager -n 20"
fi
