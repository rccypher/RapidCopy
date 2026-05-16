#!/bin/bash
# RapidCopy Update Script
# Pulls latest code from GitHub and rebuilds the Docker container.
#
# This script is called by the update_server.py sidecar.
# It should be run from the RapidCopy directory.

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAPIDCOPY_DIR="${RAPIDCOPY_PATH:-/opt/RapidCopy}"
COMPOSE_FILE="${RAPIDCOPY_DIR}/docker-compose.yml"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
}

# Verify we're in the right directory
if [ ! -f "${COMPOSE_FILE}" ]; then
    error "docker-compose.yml not found at ${COMPOSE_FILE}"
    error "Set RAPIDCOPY_PATH environment variable to the correct path"
    exit 1
fi

cd "${RAPIDCOPY_DIR}"

log "Starting RapidCopy update..."
log "Working directory: $(pwd)"

# Step 1: Fetch and pull latest changes
log "Fetching latest changes from GitHub..."
git fetch origin

# Get current and remote commit hashes
CURRENT_COMMIT=$(git rev-parse HEAD)
REMOTE_COMMIT=$(git rev-parse origin/main 2>/dev/null || git rev-parse origin/master)

if [ "${CURRENT_COMMIT}" = "${REMOTE_COMMIT}" ]; then
    log "Already up to date (commit: ${CURRENT_COMMIT:0:8})"
    log "Skipping rebuild since no changes detected."
    exit 0
fi

log "Current commit: ${CURRENT_COMMIT:0:8}"
log "Remote commit: ${REMOTE_COMMIT:0:8}"

# Step 2: Pull changes
log "Pulling changes..."
git pull origin main 2>/dev/null || git pull origin master

# Step 3: Build new Docker image
log "Building Docker image (this may take a few minutes)..."
docker-compose build --no-cache

# Step 4: Restart containers
log "Restarting containers..."
docker-compose down
docker-compose up -d

# Step 5: Verify container is running
log "Waiting for container to start..."
sleep 5

if docker-compose ps | grep -q "Up"; then
    log "Container is running"
else
    error "Container failed to start"
    docker-compose logs --tail=50
    exit 1
fi

# Step 6: Clean up old images (optional)
log "Cleaning up old Docker images..."
docker image prune -f || true

NEW_COMMIT=$(git rev-parse HEAD)
log "Update complete!"
log "Updated from ${CURRENT_COMMIT:0:8} to ${NEW_COMMIT:0:8}"
