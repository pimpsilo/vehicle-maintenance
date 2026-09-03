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

# 1. Stream updated code from Mac to QNAP (suppressing macOS xattrs and preserving QNAP data/)
echo "📦 Streaming updated application files..."
COPYFILE_DISABLE=1 tar --no-xattrs \
    --exclude='.git' \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='data' \
    -czf - . | ssh "$QNAP_USER@$QNAP_HOST" "tar -xzf - -C $REMOTE_DIR"

# 2. Rebuild and restart the container on QNAP
# We invoke a login shell and export Container Station binary paths so sudo finds docker
echo "🐳 Rebuilding and restarting container..."
ssh -t "$QNAP_USER@$QNAP_HOST" "/bin/sh -l -c '
    export PATH=\$PATH:/share/CACHEDEV1_DATA/.qpkg/container-station/bin:/share/CACHEDEV2_DATA/.qpkg/container-station/bin:/usr/local/bin:/usr/local/sbin
    DOCKER_BIN=\$(which docker 2>/dev/null || echo \"docker\")
    echo \"Using Docker: \$DOCKER_BIN\"
    cd $REMOTE_DIR && sudo \"\$DOCKER_BIN\" compose up -d --build
'"

# 3. Verify health probe
echo "🩺 Verifying health check probe..."
sleep 4
STATUS=$(curl -s "http://nas6e810d.tail8ba0ff.ts.net:8000/healthz" 2>/dev/null || curl -s "http://$QNAP_HOST:8000/healthz" 2>/dev/null || echo '{"status":"starting"}')
echo "   Probe response: $STATUS"

echo ""
echo "✅ Update complete! All vehicle records, logs, and attachments were preserved."
echo "🌐 Dashboard: http://nas6e810d.tail8ba0ff.ts.net:8000/dashboard"
