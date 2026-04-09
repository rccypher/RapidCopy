# RapidCopy

**A modernized fork of [SeedSync](https://github.com/ipsingh06/seedsync)** - Fast, corruption-proof file synchronization from remote Linux servers using rclone over SFTP.

<p align="center">
  <a href="https://hub.docker.com/r/rccypher/rapidcopy">
    <img src="https://img.shields.io/docker/pulls/rccypher/rapidcopy" alt="Docker Pulls">
  </a>
  <a href="https://github.com/rccypher/RapidCopy">
    <img src="https://img.shields.io/badge/python-3.11-blue" alt="Python 3.11">
  </a>
  <a href="https://github.com/rccypher/RapidCopy">
    <img src="https://img.shields.io/badge/angular-18.2-red" alt="Angular 18.2">
  </a>
  <a href="https://github.com/rccypher/RapidCopy">
    <img src="https://img.shields.io/badge/code%20style-ruff-purple" alt="Ruff">
  </a>
  <a href="https://github.com/rccypher/RapidCopy">
    <img src="https://img.shields.io/badge/type%20checked-mypy-green" alt="Mypy">
  </a>
  <a href="https://github.com/rccypher/RapidCopy/blob/master/LICENSE.txt">
    <img src="https://img.shields.io/github/license/rccypher/RapidCopy" alt="License">
  </a>
</p>

## What is RapidCopy?

RapidCopy automatically syncs files from a remote Linux server to your local machine. It connects via SSH, monitors remote directories for new files, and downloads them using [rclone](https://rclone.org/) over SFTP with built-in integrity verification. Once downloaded, files are validated via chunk-level checksums and optionally extracted, all managed through a modern web UI.

You don't need to install anything on the remote server. All you need are SSH credentials.

## Features

### Corruption-Proof Transfers

RapidCopy uses a multi-layered integrity strategy to guarantee every downloaded file is bit-perfect:

- **Single-stream SFTP** - Avoids the parallel-stream reassembly corruption that plagues multi-threaded download tools
- **rclone `--checksum`** - MD5 verification after each transfer, with automatic retry (3 attempts)
- **Atomic staging** - Files download to a staging directory with a `.lftp` suffix, then atomically rename on completion
- **Post-download validation** - Chunk-level xxHash checksums compared between remote and local copies
- **Automatic corrupt chunk re-download** - Only the bad bytes are re-fetched, not the entire file

### Multiple Path Pairs

Sync multiple remote/local directory combinations in a single instance. Each path pair operates independently with its own scanner, auto-queue settings, and file tracking.

- Configure pairs via the Settings UI or `path_pairs.json`
- Per-pair download concurrency limits
- Per-pair auto-queue control
- Dashboard statistics showing file counts per path pair

### Post-Download File Validation

Automatically verify file integrity after download by comparing chunk-level checksums between remote and local copies.

- **Chunk-based validation** - Files are split into chunks and each chunk is checksummed independently
- **Supported algorithms** - xxHash128 (default, fastest), MD5, SHA-256, SHA-1
- **Adaptive chunk sizing** - Chunk size scales based on file size, network speed, and failure rate
- **Automatic retry** - Corrupt chunks are re-downloaded up to a configurable number of retries
- **File states** - Files progress through VALIDATING, VALIDATED, or CORRUPT states in the UI

### Network Mount Support (NFS/CIFS)

Mount NFS or SMB/CIFS network shares directly from the UI. Download files straight to NAS or network storage.

### Hot-Reload Configuration

Change settings through the web UI without restarting the container. Download limits, rate limits, and per-directory caps take effect immediately.

### Dark Mode

Toggle between light and dark themes from the sidebar.

### Modern Tech Stack

- **Python 3.11** with modern type syntax
- **Angular 18.2** frontend
- **rclone** transfer backend (replaced lftp)
- **Full type safety** - Mypy with 0 errors
- **Ruff linting** - 0 issues
- **Playwright E2E tests**
- **Docker multi-stage build**

## How It Works

1. Install RapidCopy via Docker
2. Configure SSH credentials for your remote server
3. Set up path pairs mapping remote directories to local destinations
4. RapidCopy scans remote directories on a configurable interval (default 30s)
5. New files are auto-queued for download (or manually queued via UI)
6. rclone handles the transfer over SFTP with checksum verification
7. Downloaded files are validated via chunk-level checksums
8. Monitor everything through the web UI at port 8800

## Supported Platforms

* Linux (native or Docker)
* Raspberry Pi (v2, v3, v4, v5)
* Windows (via Docker)
* macOS (via Docker)

## Quick Start

### Docker (Recommended)

```bash
docker run -d \
  --name rapidcopy \
  --restart unless-stopped \
  -p 8800:8800 \
  -v /path/to/config:/config \
  -v /path/to/downloads:/downloads \
  -v ~/.ssh/id_rsa:/home/rapidcopy/.ssh/id_rsa:ro \
  rccypher/rapidcopy:latest
```

For multiple download destinations (e.g., TV + Movies):

```bash
docker run -d \
  --name rapidcopy \
  --restart unless-stopped \
  -p 8800:8800 \
  -v /path/to/config:/config \
  -v /mnt/media:/mnt/media \
  -v ~/.ssh/id_rsa:/home/rapidcopy/.ssh/id_rsa:ro \
  rccypher/rapidcopy:latest
```

Access the web UI at `http://localhost:8800`

### Docker Compose

```yaml
services:
  rapidcopy:
    image: rccypher/rapidcopy:latest
    container_name: rapidcopy
    restart: unless-stopped
    ports:
      - "8800:8800"
    volumes:
      - ./config:/config
      - /path/to/downloads:/downloads
      - ~/.ssh/id_rsa:/home/rapidcopy/.ssh/id_rsa:ro
```

## Configuration

RapidCopy is configured via the web UI Settings page. Changes take effect immediately without restart.

### Download Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `num_max_parallel_downloads` | `8` | Total simultaneous downloads across all directories |
| `num_max_parallel_downloads_per_path` | `4` | Maximum simultaneous downloads per path pair |
| `rate_limit` | `0` (unlimited) | Download speed limit (`1M` = 1 MB/s, `500K` = 500 KB/s) |
| `num_max_parallel_files_per_download` | `4` | Parallel files within a single directory download |

### Path Pairs

Configured via the Settings UI or `path_pairs.json`:

```json
{
  "version": 1,
  "path_pairs": [
    {
      "id": "unique-id-001",
      "name": "TV Shows",
      "remote_path": "/seedbox/complete/sonarr",
      "local_path": "/downloads/tv",
      "enabled": true,
      "auto_queue": true
    },
    {
      "id": "unique-id-002",
      "name": "Movies",
      "remote_path": "/seedbox/complete/radarr",
      "local_path": "/downloads/movies",
      "enabled": true,
      "auto_queue": true
    }
  ]
}
```

### Validation Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | `True` | Enable post-download file validation |
| `algorithm` | `xxh128` | Hash algorithm (`xxh128`, `md5`, `sha256`, `sha1`) |
| `default_chunk_size` | `52428800` (50MB) | Base chunk size for validation |
| `max_chunk_size` | `104857600` (100MB) | Maximum chunk size |
| `max_retries` | `3` | Retry attempts for corrupt chunks |
| `enable_adaptive_sizing` | `True` | Scale chunk size based on conditions |

### Logging

| Setting | Description | Values |
|---------|-------------|--------|
| `log_level` | Minimum log level | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |

## Development

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Node.js 18+ (for Angular frontend)
- rclone (for local development)

### Running Tests

```bash
# Python unit tests
cd src/python
poetry run pytest tests/unittests/ -v

# Angular unit tests
cd src/angular
npx ng test

# Playwright E2E tests
cd src/e2e-playwright
npx playwright test
```

### Code Quality

| Tool | Status | Description |
|------|--------|-------------|
| **Ruff** | 0 issues | Fast Python linter |
| **Mypy** | 0 errors | Static type checking |
| **Pytest** | 474 passing | Python unit tests |
| **Playwright** | 62 passing | E2E UI tests |

## Project Structure

```
RapidCopy/
├── src/
│   ├── python/              # Python backend
│   │   ├── common/          # Shared utilities, config, models
│   │   ├── controller/      # Business logic, scanning, validation
│   │   ├── rclone/          # rclone transfer backend
│   │   ├── model/           # Data models (ModelFile, states)
│   │   ├── ssh/             # SSH utilities
│   │   ├── system/          # File system operations
│   │   ├── web/             # Web server, API, SSE streaming
│   │   └── tests/           # Python test suite
│   ├── angular/             # Web frontend (Angular 18)
│   ├── e2e-playwright/      # Playwright E2E tests
│   └── docker/              # Docker build configs
├── doc/                     # Documentation
├── Dockerfile               # Multi-stage Docker build
└── docker-compose.yml       # Compose template
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Ensure all tests pass
4. Ensure code passes linting (`ruff check .`) and type checking (`mypy .`)
5. Submit a pull request

See [Developer Readme](doc/DeveloperReadme.md) for detailed setup instructions.

## Report an Issue

Please report issues on the [issues page](../../issues).
Include logs if possible:
- Docker: `docker logs <container id>`

## Credits

RapidCopy is based on [SeedSync](https://github.com/ipsingh06/seedsync) by [ipsingh06](https://github.com/ipsingh06).

## License

RapidCopy is distributed under Apache License Version 2.0.
See [LICENSE.txt](LICENSE.txt) for more information.
