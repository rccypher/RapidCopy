# RapidCopy Deployment Guide

This guide covers deploying RapidCopy on Ubuntu 24 Server, including migrating from existing SeedSync installations.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Migrating from SeedSync](#migrating-from-seedsync)
- [SSH Key Authentication](#ssh-key-authentication)
- [Multi-Path Configuration](#multi-path-configuration)
- [Docker Compose](#docker-compose)
- [Systemd Integration](#systemd-integration)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

- Ubuntu 24.04 LTS (or compatible Linux distribution)
- Docker installed and running
- SSH access to the server
- Network access to your remote seedbox/server

### Install Docker (if not already installed)

```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sudo sh

# Add your user to docker group
sudo usermod -aG docker $USER

# Log out and back in, then verify
docker --version
```

---

## Quick Start

### 1. Create directories

```bash
sudo mkdir -p /opt/rapidcopy/{config,downloads}
sudo chown -R 1000:1000 /opt/rapidcopy
```

### 2. Build or pull the image

```bash
# Option A: Build from source
git clone https://github.com/rccypher/RapidCopy.git
cd RapidCopy
docker build -t rapidcopy:latest .

# Option B: Pull from registry (if available)
# docker pull ghcr.io/rccypher/rapidcopy:latest
```

### 3. Run the container

```bash
docker run -d \
  --name rapidcopy \
  --restart unless-stopped \
  -p 8800:8800 \
  -v /opt/rapidcopy/config:/config \
  -v /path/to/downloads:/downloads \
  -e PUID=1000 \
  -e PGID=1000 \
  rapidcopy:latest
```

### 4. Access the web interface

Open `http://YOUR_SERVER_IP:8800` in your browser and configure your settings.

---

## Migrating from SeedSync

If you're replacing existing SeedSync instances with RapidCopy, follow these steps:

### Step 1: Backup existing configurations

```bash
# List running SeedSync containers
docker ps | grep -i seedsync

# Create backup directory
mkdir -p ~/seedsync-backup

# Backup config from each container (adjust container names as needed)
docker cp seedsync-1:/config ~/seedsync-backup/config-1
docker cp seedsync-2:/config ~/seedsync-backup/config-2

# View configs to note important settings
cat ~/seedsync-backup/config-1/settings.cfg
cat ~/seedsync-backup/config-2/settings.cfg
```

**Note these values from each SeedSync instance:**
- `remote_address` - Remote server hostname/IP
- `remote_username` - SSH/SFTP username
- `remote_password` - SSH/SFTP password (if using password auth)
- `remote_port` - SSH port (usually 22)
- `remote_path` - Remote directory path
- `local_path` - Local download path

### Step 2: Stop existing SeedSync containers

```bash
# Stop containers
docker stop seedsync-1 seedsync-2

# Optionally remove them (keep for rollback option)
# docker rm seedsync-1 seedsync-2
```

### Step 3: Create RapidCopy configuration

```bash
# Create directories
sudo mkdir -p /opt/rapidcopy/config
sudo chown -R 1000:1000 /opt/rapidcopy
```

Create `/opt/rapidcopy/config/settings.cfg`:

```ini
[General]
debug = False
verbose = False
log_level = INFO

[Lftp]
remote_address = YOUR_REMOTE_SERVER
remote_username = YOUR_USERNAME
remote_password = YOUR_PASSWORD
remote_port = 22
remote_path = /path/from/seedsync-1
local_path = /downloads/dest-1
remote_path_to_scan_script = /tmp
use_ssh_key = False
num_max_parallel_downloads = 2
num_max_parallel_files_per_download = 4
num_max_connections_per_root_file = 4
num_max_connections_per_dir_file = 4
num_max_total_connections = 16
use_temp_file = False
rate_limit = 0

[Controller]
interval_ms_remote_scan = 30000
interval_ms_local_scan = 10000
interval_ms_downloading_scan = 1000
extract_path = /tmp
use_local_path_as_extract_path = True

[Web]
port = 8800

[AutoQueue]
enabled = True
patterns_only = False
auto_extract = True

[PathPairs]
pair_1_remote = /path/from/seedsync-1
pair_1_local = /downloads/dest-1
pair_1_label = Server1
pair_2_remote = /path/from/seedsync-2
pair_2_local = /downloads/dest-2
pair_2_label = Server2
```

### Step 4: Run RapidCopy

```bash
docker run -d \
  --name rapidcopy \
  --restart unless-stopped \
  -p 8800:8800 \
  -v /opt/rapidcopy/config:/config \
  -v /path/to/downloads1:/downloads/dest-1 \
  -v /path/to/downloads2:/downloads/dest-2 \
  -e PUID=1000 \
  -e PGID=1000 \
  rapidcopy:latest
```

### Step 5: Verify and cleanup

```bash
# Check container status
docker ps | grep rapidcopy
docker logs -f rapidcopy

# Access web UI
curl -I http://localhost:8800

# Once verified, remove old containers
docker rm seedsync-1 seedsync-2
```

---

## SSH Key Authentication

RapidCopy supports password-less SSH key authentication for secure, automated connections.

### Setting up SSH keys

#### 1. Generate an SSH key pair (if you don't have one)

```bash
# Generate a new key without passphrase (required for automated use)
ssh-keygen -t ed25519 -f ~/.ssh/rapidcopy_key -N ""

# Or use RSA if ed25519 is not supported
ssh-keygen -t rsa -b 4096 -f ~/.ssh/rapidcopy_key -N ""
```

> **Important:** The key must NOT have a passphrase for automated authentication to work.

#### 2. Copy the public key to your remote server

```bash
ssh-copy-id -i ~/.ssh/rapidcopy_key.pub user@your-seedbox.com

# Or manually append to authorized_keys
cat ~/.ssh/rapidcopy_key.pub | ssh user@your-seedbox.com "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

#### 3. Test the connection

```bash
ssh -i ~/.ssh/rapidcopy_key user@your-seedbox.com
# Should connect without asking for password
```

#### 4. Mount the key in Docker

```bash
docker run -d \
  --name rapidcopy \
  --restart unless-stopped \
  -p 8800:8800 \
  -v /opt/rapidcopy/config:/config \
  -v /path/to/downloads:/downloads \
  -v ~/.ssh/rapidcopy_key:/root/.ssh/id_rsa:ro \
  -v ~/.ssh/rapidcopy_key.pub:/root/.ssh/id_rsa.pub:ro \
  -e PUID=1000 \
  -e PGID=1000 \
  rapidcopy:latest
```

#### 5. Enable in configuration

In your `settings.cfg` or via the web UI:

```ini
[Lftp]
use_ssh_key = True
remote_password = unused  # Can be any value, will be ignored
```

Or in the web UI: **Settings > Server > Use password-less key-based authentication** (check the box)

### SSH Key Troubleshooting

| Issue | Solution |
|-------|----------|
| "Permission denied (publickey)" | Check key permissions: `chmod 600 ~/.ssh/rapidcopy_key` |
| Key not found in container | Verify mount path: `docker exec rapidcopy ls -la /root/.ssh/` |
| Host key verification failed | Add remote host to known_hosts or set `StrictHostKeyChecking no` |
| Key has passphrase | Generate a new key without passphrase using `-N ""` |

---

## Multi-Path Configuration

RapidCopy supports syncing multiple remote/local path pairs in a single instance. This replaces the need to run multiple containers for different directory pairs.

### How it works

- Each path pair defines a remote directory and its corresponding local destination
- Files are scanned and tracked independently for each path pair
- Downloads are automatically routed to the correct local directory
- The UI shows which path pair each file belongs to

### Configuration

Path pairs are stored in `path_pairs.json` in your config directory (separate from `settings.cfg`):

Create `/opt/rapidcopy/config/path_pairs.json`:

```json
{
  "version": 1,
  "path_pairs": [
    {
      "id": "movies-001",
      "name": "Movies",
      "remote_path": "/seedbox/movies",
      "local_path": "/downloads/movies",
      "enabled": true,
      "auto_queue": true
    },
    {
      "id": "tvshows-002",
      "name": "TV Shows",
      "remote_path": "/seedbox/tv",
      "local_path": "/downloads/tv",
      "enabled": true,
      "auto_queue": true
    },
    {
      "id": "music-003",
      "name": "Music",
      "remote_path": "/seedbox/music",
      "local_path": "/downloads/music",
      "enabled": true,
      "auto_queue": false
    }
  ]
}
```

### Path pair fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier (use any string, e.g., UUID or descriptive ID) |
| `name` | Yes | Human-readable name displayed in the UI |
| `remote_path` | Yes | Full path on the remote server |
| `local_path` | Yes | Full path on the local machine (inside container) |
| `enabled` | No | Set to `false` to temporarily disable scanning (default: `true`) |
| `auto_queue` | No | Auto-queue new files for this path pair (default: `true`) |

### Volume mounts

Each local path needs a corresponding volume mount:

```bash
docker run -d \
  --name rapidcopy \
  -p 8800:8800 \
  -v /opt/rapidcopy/config:/config \
  -v /media/movies:/downloads/one \
  -v /media/tvshows:/downloads/two \
  -v /media/music:/downloads/three \
  rapidcopy:latest
```

---

## Docker Compose

For easier management, use Docker Compose:

### docker-compose.yml

```yaml
version: "3.8"

services:
  rapidcopy:
    image: rapidcopy:latest
    build:
      context: .
      dockerfile: Dockerfile
    container_name: rapidcopy
    restart: unless-stopped
    ports:
      - "8800:8800"
    volumes:
      - ./config:/config
      - /path/to/downloads:/downloads
      # For SSH key authentication:
      - ~/.ssh/rapidcopy_key:/root/.ssh/id_rsa:ro
      - ~/.ssh/rapidcopy_key.pub:/root/.ssh/id_rsa.pub:ro
    environment:
      - PUID=1000
      - PGID=1000
```

### Usage

```bash
# Start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down

# Rebuild and restart
docker-compose up -d --build
```

---

## Systemd Integration

For better integration with Ubuntu's service management:

### Create service file

```bash
sudo tee /etc/systemd/system/rapidcopy.service << 'EOF'
[Unit]
Description=RapidCopy File Sync
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/docker start rapidcopy
ExecStop=/usr/bin/docker stop rapidcopy

[Install]
WantedBy=multi-user.target
EOF
```

### Enable and manage

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable rapidcopy

# Start/stop/status
sudo systemctl start rapidcopy
sudo systemctl stop rapidcopy
sudo systemctl status rapidcopy
```

---

## Troubleshooting

### Container won't start

```bash
# Check logs
docker logs rapidcopy

# Check if port is in use
sudo netstat -tlnp | grep 8800

# Run interactively to see errors
docker run -it --rm \
  -v /opt/rapidcopy/config:/config \
  rapidcopy:latest
```

### Permission issues

```bash
# Fix ownership
sudo chown -R 1000:1000 /opt/rapidcopy
sudo chown -R 1000:1000 /path/to/downloads

# Check container user
docker exec rapidcopy id
```

### Connection issues

```bash
# Test SSH connection from container
docker exec -it rapidcopy ssh -v user@your-server.com

# Check LFTP directly
docker exec -it rapidcopy lftp -u user,password sftp://your-server.com
```

### Web UI not loading

```bash
# Check container is running
docker ps | grep rapidcopy

# Check port binding
docker port rapidcopy

# Check firewall
sudo ufw status
sudo ufw allow 8800/tcp
```

### Reset configuration

```bash
# Backup current config
cp /opt/rapidcopy/config/settings.cfg ~/settings.cfg.backup

# Remove container and recreate
docker rm -f rapidcopy
rm -rf /opt/rapidcopy/config/*

# Restart - will create default config
docker run -d --name rapidcopy ...
```

---

## Quick Reference

| Action | Command |
|--------|---------|
| Start | `docker start rapidcopy` |
| Stop | `docker stop rapidcopy` |
| Restart | `docker restart rapidcopy` |
| View logs | `docker logs -f rapidcopy` |
| Shell access | `docker exec -it rapidcopy /bin/bash` |
| Check status | `docker ps \| grep rapidcopy` |
| Update | `docker pull rapidcopy:latest && docker restart rapidcopy` |

---

## Support

- GitHub Issues: https://github.com/rccypher/RapidCopy/issues
- Documentation: https://github.com/rccypher/RapidCopy/docs
