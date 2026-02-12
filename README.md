# RapidCopy

**A modernized fork of [SeedSync](https://github.com/ipsingh06/seedsync)** - Fast file synchronization from remote Linux servers using LFTP.

<p align="center">
  <a href="https://github.com/rccypher/RapidCopy">
    <img src="https://img.shields.io/badge/python-3.11-blue" alt="Python 3.11">
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

## What's New in RapidCopy

This fork modernizes the original SeedSync codebase:

- **Python 3.11** - Upgraded from Python 3.8
- **Modern Type Hints** - Full mypy type checking with 0 errors
- **Code Quality** - Ruff linting with 0 issues
- **408 Unit Tests** - All passing
- **Modern Python Syntax** - Using `|` union types, `list[]` instead of `List[]`, etc.

## Features

* Built on top of [LFTP](http://lftp.tech/), the fastest file transfer program ever
* Web UI - track and control your transfers from anywhere
* Automatically extract your files after sync
* Auto-Queue - only sync the files you want based on pattern matching
* Delete local and remote files easily
* Fully open source!

## How it works

Install RapidCopy on a local machine. RapidCopy will connect to your remote server and sync files to the local machine as they become available.

You don't need to install anything on the remote server. All you need are the SSH credentials for the remote server.

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
  -v /path/to/downloads:/downloads \
  -v /path/to/config:/config \
  rapidcopy:latest
```

Access the web UI at `http://localhost:8800`

### From Source

See the [Developer Guide](doc/DeveloperReadme.md) for building from source.

## Development

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Node.js (for Angular frontend)

### Python Backend

```bash
cd src/python

# Run tests
docker-compose -f ../docker/test/python/compose.yml run --rm tests pytest tests/unittests/ -q

# Run linting
docker run --rm -v "$(pwd):/src" -w /src python:3.11-slim bash -c "pip install -q ruff && ruff check ."

# Run type checking
docker run --rm -v "$(pwd):/src" -w /src python:3.11-slim bash -c "pip install -q mypy types-requests && mypy ."
```

### Code Quality Standards

| Tool | Status | Description |
|------|--------|-------------|
| **Ruff** | 0 issues | Fast Python linter (replaces flake8, isort, etc.) |
| **Mypy** | 0 errors | Static type checking |
| **Pytest** | 408 passing | Unit test suite |

## Project Structure

```
RapidCopy/
├── src/
│   ├── python/           # Python backend
│   │   ├── common/       # Shared utilities
│   │   ├── controller/   # Business logic
│   │   ├── lftp/         # LFTP integration
│   │   ├── model/        # Data models
│   │   ├── ssh/          # SSH utilities
│   │   ├── system/       # File system operations
│   │   ├── web/          # Web server & API
│   │   └── tests/        # Test suite
│   ├── angular/          # Web frontend (Angular)
│   ├── docker/           # Docker configurations
│   └── e2e/              # End-to-end tests
├── doc/                  # Documentation
└── Makefile              # Build automation
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Ensure all tests pass (`make run-tests-python`)
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
