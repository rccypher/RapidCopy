# RapidCopy

**A modernized fork of [SeedSync](https://github.com/ipsingh06/seedsync)** - Fast file synchronization from remote Linux servers using LFTP.

<p align="center">
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

RapidCopy automatically syncs files from a remote Linux server to your local machine. It connects via SSH, monitors remote directories for new files, and downloads them using [LFTP](http://lftp.tech/) - the fastest file transfer program available. Once downloaded, files are optionally validated and extracted, all managed through a modern web UI.

You don't need to install anything on the remote server. All you need are SSH credentials.

## Features Added Since SeedSync

RapidCopy is a comprehensive rewrite and modernization of the original SeedSync project. The following features have been added since forking:

### Multiple Path Pairs

Sync multiple remote/local directory combinations in a single RapidCopy instance. Each path pair operates independently with its own scanner, auto-queue settings, and file tracking. Files in the dashboard are tagged with their path pair for easy identification.

- Configure pairs via the Settings UI or `path_pairs.json`
- Enable/disable individual pairs without affecting others
- Per-pair auto-queue control
- Dashboard statistics showing file counts per path pair

### Post-Download File Validation

Automatically verify file integrity after download by comparing chunk-level checksums between remote and local copies. This catches silent corruption, incomplete transfers, and bit-rot before you rely on the downloaded files.

- **Chunk-based validation** - Files are split into chunks and each chunk is checksummed independently, allowing identification of exactly which portions are corrupt
- **Supported algorithms** - MD5 (default), SHA-256, SHA-1
- **Adaptive chunk sizing** - Chunk size automatically scales based on file size (larger chunks for bigger files), network speed, and historical failure rate
- **Automatic retry** - Corrupt chunks are re-downloaded and re-validated up to a configurable number of retries
- **File states** - Files progress through VALIDATING, VALIDATED, or CORRUPT states with dedicated status icons in the UI
- **Manual validation** - Trigger validation on any downloaded file via the dashboard

### Network Mount Support (NFS/CIFS)

Mount NFS or SMB/CIFS network shares directly from the RapidCopy UI. Download files straight to NAS or network storage without intermediate local copies.

- Configure mounts via the Settings UI
- Mount/unmount/test actions from the web interface
- Supports both NFS and CIFS/SMB protocols

### Dark Mode

Toggle between light and dark themes from the sidebar. Theme preference is persisted across sessions.

### Download Rate Limiting

Control bandwidth usage with configurable rate limits to prevent saturating your connection. Set limits like `10M` (10 MB/s), `500K` (500 KB/s), or `0` for unlimited.

### Configurable Logging

Set log verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL) and optionally enable JSON-formatted log output for integration with log aggregation systems like ELK or Splunk.

### Modern Tech Stack

- **Python 3.11** - Upgraded from Python 3.8 with modern syntax (`|` union types, `list[]` generics)
- **Angular 18.2** - Frontend completely rewritten from Angular 4.x
- **Full type safety** - Mypy type checking with 0 errors
- **Ruff linting** - 0 issues
- **Playwright E2E tests** - Migrated from Protractor (which is deprecated)
- **Docker multi-stage build** - Single Dockerfile for streamlined deployment
- **JSON-based remote scanning** - Replaced pickle serialization for security (prevents RCE)
- **408 unit tests + 62 E2E tests** - All passing

### Self-Update Service

Optional auto-update support via an external update server. Check for and apply updates without manual intervention.

## How It Works

1. Install RapidCopy on your local machine (or run via Docker)
2. Configure SSH credentials for your remote server
3. Set up path pairs mapping remote directories to local destinations
4. RapidCopy scans remote directories on a configurable interval
5. New files are auto-queued for download (or manually queued)
6. LFTP handles the actual transfer with parallel connections
7. Downloaded files are optionally validated and/or extracted
8. Monitor everything through the web UI

## Supported Platforms

* Linux (native)
* Raspberry Pi (v2, v3, v4, v5)
* Windows (via Docker)
* macOS (via Docker)

## Quick Start

### Docker (Recommended)

```bash
docker run -d \
  --name rapidcopy \
  -p 8800:8800 \
  -v /path/to/config:/config \
  -v /path/to/downloads:/downloads \
  -v ~/.ssh:/home/rapidcopy/.ssh:ro \
  rapidcopy:latest
```

For multiple download destinations, add additional volume mounts:

```bash
docker run -d \
  --name rapidcopy \
  -p 8800:8800 \
  -v /path/to/config:/config \
  -v /path/to/tv_downloads:/downloads/tv_shows \
  -v /path/to/movie_downloads:/downloads/movies \
  -v ~/.ssh:/home/rapidcopy/.ssh:ro \
  rapidcopy:latest
```

Access the web UI at `http://localhost:8800`

### Docker Compose

```yaml
services:
  rapidcopy:
    build: .
    image: rapidcopy:latest
    container_name: rapidcopy
    restart: unless-stopped
    ports:
      - "8800:8800"
    volumes:
      - ./config:/config
      - /path/to/downloads:/downloads
      - ~/.ssh:/home/rapidcopy/.ssh:ro
```

## Configuration

RapidCopy is configured via the web UI Settings page or by editing the config files directly.

### Path Pairs

Configured via the Settings UI or `path_pairs.json` in your config directory:

```json
{
  "version": 1,
  "path_pairs": [
    {
      "id": "unique-id-001",
      "name": "Movies",
      "remote_path": "/seedbox/complete/movies",
      "local_path": "/downloads/movies",
      "enabled": true,
      "auto_queue": true
    },
    {
      "id": "unique-id-002",
      "name": "TV Shows",
      "remote_path": "/seedbox/complete/tv",
      "local_path": "/downloads/tv",
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
| `algorithm` | `md5` | Hash algorithm (`md5`, `sha256`, `sha1`) |
| `default_chunk_size` | `52428800` (50MB) | Base chunk size for validation |
| `max_chunk_size` | `104857600` (100MB) | Maximum chunk size after adaptive scaling |
| `validate_after_file` | `True` | Validate immediately after each file completes |
| `max_retries` | `3` | Number of retry attempts for corrupt chunks |
| `enable_adaptive_sizing` | `True` | Automatically scale chunk size based on file size and network conditions |

### Rate Limiting

| Setting | Description | Example |
|---------|-------------|---------|
| `rate_limit` | Maximum download speed | `10M` (10 MB/s), `500K` (500 KB/s), `0` (unlimited) |

### Logging

| Setting | Description | Values |
|---------|-------------|--------|
| `log_level` | Minimum log level | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `log_format` | Log output format | `standard`, `json` |

## Development

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Node.js 18+ (for Angular frontend)

### Running Tests

```bash
# Python unit tests (via Docker)
cd src/python
docker-compose -f ../docker/test/python/compose.yml run --rm tests pytest tests/unittests/ -q

# Angular unit tests
cd src/angular
npx ng test

# Playwright E2E tests (start dev server first)
cd src/angular && npx ng serve --port 8800 &
cd src/e2e-playwright && npx playwright test --project=ui-only
```

### Code Quality

| Tool | Status | Description |
|------|--------|-------------|
| **Ruff** | 0 issues | Fast Python linter |
| **Mypy** | 0 errors | Static type checking |
| **Pytest** | 408 passing | Python unit tests |
| **Playwright** | 62 passing | E2E UI tests |

## Project Structure

```
RapidCopy/
├── src/
│   ├── python/              # Python backend
│   │   ├── common/          # Shared utilities, config, models
│   │   ├── controller/      # Business logic, scanning, validation
│   │   ├── lftp/            # LFTP integration
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

## To-Do

- [ ] Add file validation settings to the Settings UI (validation is currently only configurable via `settings.cfg`)
- [ ] Review all config settings and ensure they are all available from the Settings UI

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
- Native: `~/.rapidcopy/log/rapidcopy.log`

## Credits

RapidCopy is based on [SeedSync](https://github.com/ipsingh06/seedsync) by [ipsingh06](https://github.com/ipsingh06).

## License

RapidCopy is distributed under Apache License Version 2.0.
See [LICENSE.txt](LICENSE.txt) for more information.
