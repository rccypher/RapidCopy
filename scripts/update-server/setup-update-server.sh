#!/bin/bash
# RapidCopy Update Server Setup Script
# This script installs and configures the auto-update sidecar service.
#
# Prerequisites:
#   - RapidCopy cloned to /opt/RapidCopy
#   - Docker and docker-compose installed
#   - Python 3 installed
#
# Usage:
#   sudo ./setup-update-server.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    error "This script must be run as root (use sudo)"
fi

RAPIDCOPY_PATH="/opt/RapidCopy"
SCRIPTS_PATH="${RAPIDCOPY_PATH}/scripts/update-server"
SERVICE_FILE="/etc/systemd/system/rapidcopy-updater.service"
ENV_FILE="/etc/rapidcopy-updater.env"

# Check if RapidCopy is installed
if [ ! -d "${RAPIDCOPY_PATH}" ]; then
    error "RapidCopy not found at ${RAPIDCOPY_PATH}. Please clone or move it there first."
fi

if [ ! -f "${SCRIPTS_PATH}/update_server.py" ]; then
    error "Update server script not found at ${SCRIPTS_PATH}/update_server.py"
fi

log "Setting up RapidCopy Update Server..."

# Generate a secure token if not already set
if [ ! -f "${ENV_FILE}" ]; then
    log "Generating secure update token..."
    TOKEN=$(openssl rand -hex 32)
    
    cat > "${ENV_FILE}" << EOF
# RapidCopy Update Server Configuration
# Generated on $(date)

# Security token for update requests
# This token must also be set in docker-compose.yml
UPDATE_TOKEN=${TOKEN}

# Path to RapidCopy installation
RAPIDCOPY_PATH=${RAPIDCOPY_PATH}

# Port for update server (default: 8801)
UPDATE_SERVER_PORT=8801
EOF
    
    chmod 600 "${ENV_FILE}"
    log "Environment file created at ${ENV_FILE}"
    
    echo ""
    echo "========================================"
    echo "IMPORTANT: Save this token!"
    echo "========================================"
    echo ""
    echo "UPDATE_TOKEN=${TOKEN}"
    echo ""
    echo "Add this to your docker-compose.yml or .env file:"
    echo "  UPDATE_TOKEN=${TOKEN}"
    echo ""
    echo "========================================"
else
    log "Environment file already exists at ${ENV_FILE}"
    warn "To regenerate the token, delete ${ENV_FILE} and run this script again"
fi

# Make scripts executable
log "Setting script permissions..."
chmod +x "${SCRIPTS_PATH}/update_server.py"
chmod +x "${SCRIPTS_PATH}/update-rapidcopy.sh"

# Install systemd service
log "Installing systemd service..."
cp "${SCRIPTS_PATH}/rapidcopy-updater.service" "${SERVICE_FILE}"

# Reload systemd
log "Reloading systemd..."
systemctl daemon-reload

# Enable and start service
log "Enabling and starting rapidcopy-updater service..."
systemctl enable rapidcopy-updater
systemctl start rapidcopy-updater

# Check status
if systemctl is-active --quiet rapidcopy-updater; then
    log "Service started successfully!"
else
    warn "Service may not have started correctly. Check with: systemctl status rapidcopy-updater"
fi

echo ""
log "Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Add UPDATE_TOKEN to your docker-compose.yml or .env file"
echo "  2. Rebuild and restart RapidCopy: docker-compose up -d --build"
echo "  3. Visit the About page in RapidCopy to use the update feature"
echo ""
echo "Useful commands:"
echo "  View logs:    journalctl -u rapidcopy-updater -f"
echo "  Check status: systemctl status rapidcopy-updater"
echo "  Restart:      systemctl restart rapidcopy-updater"
echo "  Test health:  curl http://localhost:8801/health"
echo ""
