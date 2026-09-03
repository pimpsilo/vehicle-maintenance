#!/usr/bin/env bash
# ==============================================================================
# update_qnap.sh - 1-Click Update Script for QNAP Container Station
# ==============================================================================
# Run this script from your Mac terminal whenever you make code or template changes:
#   ./scripts/update_qnap.sh
# ==============================================================================
set -e

QNAP_USER="${QNAP_USER:-admin1}"
QNAP_HOST="${QNAP_HOST:-100.91.20.86}"
REMOTE_DIR="/share/Container/vehicle_maintenance"

echo "🚗 Updating Vehicle Maintenance Tracker on QNAP ($QNAP_USER@$QNAP_HOST)..."

# 1. Stream updated code from Mac to QNAP
# IMPORTANT: --exclude='data' ensures your active QNAP database is never overwritten by local files
echo "📦 Streaming updated application files..."
tar --exclude='.git' \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='data' \
    -czf - . | ssh "$QNAP_USER@$QNAP_HOST" "tar -xzf - -C $REMOTE_DIR"

# 2. Rebuild and restart the container on QNAP
echo "🐳 Rebuilding and restarting container..."
ssh -t "$QNAP_USER@$QNAP_HOST" "cd $REMOTE_DIR && sudo docker compose up -d --build"

# 3. Verify health probe
echo "🩺 Verifying health check probe..."
sleep 4
STATUS=$(curl -s "http://nas6e810d.tail8ba0ff.ts.net:8000/healthz" 2>/dev/null || curl -s "http://$QNAP_HOST:8000/healthz" 2>/dev/null || echo '{"status":"starting"}')
echo "   Probe response: $STATUS"

echo ""
echo "✅ Update complete! All vehicle records, logs, and attachments were preserved."
echo "🌐 Dashboard: http://nas6e810d.tail8ba0ff.ts.net:8000/dashboard"
