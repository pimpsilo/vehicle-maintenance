#!/usr/bin/env bash
# ==============================================================================
# update_qnap.sh - 1-Click Update Script for QNAP Container Station
# ==============================================================================
# Run this script from your Mac terminal whenever you make code or template changes:
#   ./scripts/update_qnap.sh
# ==============================================================================
set -e

QNAP_USER="${QNAP_USER:-admin1}"
QNAP_HOST="${QNAP_HOST:-nas6e810d.tail8ba0ff.ts.net}"
REMOTE_DIR="/share/Container/vehicle_maintenance"

# SSH ControlMaster connection multiplexing (prompts for password ONCE only)
SOCKET_DIR="/tmp/ssh-qnap-$$"
mkdir -p "$SOCKET_DIR"
CONTROL_PATH="$SOCKET_DIR/cm-%r@%h:%p"
SSH_OPTS=(-o "ControlMaster=auto" -o "ControlPath=$CONTROL_PATH" -o "ControlPersist=120s")

cleanup() {
    ssh -O exit -o "ControlPath=$CONTROL_PATH" "$QNAP_USER@$QNAP_HOST" 2>/dev/null || true
    rm -rf "$SOCKET_DIR" 2>/dev/null || true
}
trap cleanup EXIT

echo "🚗 Updating Vehicle Maintenance Tracker on QNAP ($QNAP_USER@$QNAP_HOST)..."

# 1. Stream updated code from Mac to QNAP (suppressing macOS xattrs and preserving QNAP data/)
echo "📦 Streaming updated application files..."
COPYFILE_DISABLE=1 tar --no-xattrs \
    --exclude='.git' \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='data' \
    -czf - . | ssh "${SSH_OPTS[@]}" "$QNAP_USER@$QNAP_HOST" "tar -xzf - -C $REMOTE_DIR"

# 2. If Google Calendar token exists on Mac, sync it safely into data/ without touching the database
if [ -f "data/gcal_token.json" ]; then
    echo "🔑 Syncing Google Calendar OAuth token to QNAP..."
    scp "${SSH_OPTS[@]}" -q data/gcal_token.json "$QNAP_USER@$QNAP_HOST:$REMOTE_DIR/data/gcal_token.json"
fi

# 3. Rebuild and restart the container on QNAP
# We invoke a login shell and export Container Station binary paths so sudo finds docker
echo "🐳 Rebuilding and restarting container..."
ssh "${SSH_OPTS[@]}" -t "$QNAP_USER@$QNAP_HOST" "/bin/sh -l -c '
    export PATH=\$PATH:/share/CACHEDEV1_DATA/.qpkg/container-station/bin:/share/CACHEDEV2_DATA/.qpkg/container-station/bin:/usr/local/bin:/usr/local/sbin
    DOCKER_BIN=\$(which docker 2>/dev/null || echo \"docker\")
    echo \"Using Docker: \$DOCKER_BIN\"
    cd $REMOTE_DIR && sudo \"\$DOCKER_BIN\" compose up -d --build
'"

# 4. Verify health probe & new endpoints
echo "🩺 Verifying container health..."
sleep 5
STATUS=$(curl -s --connect-timeout 5 "http://nas6e810d.tail8ba0ff.ts.net:8000/healthz" 2>/dev/null || echo '{"status":"starting"}')
echo "   Health probe response: $STATUS"

echo "🔍 Verifying maintenance alerts engine..."
ALERTS=$(curl -s --connect-timeout 5 "http://nas6e810d.tail8ba0ff.ts.net:8000/api/v1/notifications/alerts" 2>/dev/null || echo 'not ready')
if echo "$ALERTS" | grep -q "\["; then
    echo "   Alerts API active: OK"
else
    echo "   Alerts API response: $ALERTS"
fi

echo ""
echo "✅ Update complete! All vehicle records, logs, and attachments were preserved."
echo "🌐 Dashboard: http://nas6e810d.tail8ba0ff.ts.net:8000/dashboard"
echo "📱 Mobile Portal: http://nas6e810d.tail8ba0ff.ts.net:8000/v"
