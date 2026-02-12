[TOC]

# RapidCopy Developer Guide

This guide covers setting up the development environment for RapidCopy.

## Tech Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Backend | Python | 3.11+ |
| Frontend | Angular | 4.x (upgrade to 18 planned) |
| Linting | Ruff | 0.4+ |
| Type Checking | Mypy | 1.10+ |
| Testing | Pytest | 8.0+ |
| Build | Docker, Make | - |

## Quick Start (Docker-based)

The recommended approach uses Docker containers for consistent environments.

### Prerequisites

- Docker & Docker Compose
- Git
- Make (optional, for build automation)

### Run Python Tests

```bash
cd src/python
docker-compose -f ../docker/test/python/compose.yml run --rm tests pytest tests/unittests/ -q
```

### Run Linting

```bash
cd src/python
docker run --rm -v "$(pwd):/src" -w /src python:3.11-slim bash -c "pip install -q ruff && ruff check ."
```

### Run Type Checking

```bash
cd src/python
docker run --rm -v "$(pwd):/src" -w /src python:3.11-slim bash -c "pip install -q mypy types-requests && mypy ."
```

---

# Full Environment Setup

## Install Dependencies

### 1. Node.js
Install [Node.js](https://nodejs.org/) (v18+ recommended)

### 2. Poetry (Python Package Manager)
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

### 3. Docker & Docker Compose
- [Docker Installation](https://docs.docker.com/engine/install/)
- [Docker Compose](https://docs.docker.com/compose/install/)

### 4. Docker Buildx (for multi-arch builds)
```bash
docker buildx create --name mybuilder --driver docker-container
docker buildx use mybuilder
docker buildx inspect --bootstrap
```

### 5. System Dependencies (Linux/Debian)
```bash
sudo apt-get install -y lftp python3-dev rar jq
```

## Fetch Code
```bash
git clone git@github.com:rccypher/RapidCopy.git
cd RapidCopy
```

## Setup Python Environment
```bash
cd src/python
poetry install
```

## Setup Angular Environment
```bash
cd src/angular
npm install
```

## Setup E2E Tests
```bash
cd src/e2e
npm install
```

---

# Development

## Python Backend

### Code Quality Standards

All Python code must pass:
- **Ruff** - Linting (0 issues required)
- **Mypy** - Type checking (0 errors required)
- **Pytest** - All tests passing

### Running Locally

```bash
cd src/python
mkdir -p build/config
poetry run python seedsync.py -c build/config --html ../angular/dist --scanfs build/scanfs
```

### Build scanfs
```bash
make scanfs
```

## Angular Frontend

### Development Server
```bash
cd src/angular
npm start
# or
node_modules/@angular/cli/bin/ng serve
```

Dev server runs at [http://localhost:4200](http://localhost:4200)

### Build
```bash
cd src/angular
npm run build
```

---

# Testing

## Python Unit Tests

### Using Docker (Recommended)
```bash
cd src/python
docker-compose -f ../docker/test/python/compose.yml run --rm tests pytest tests/unittests/ -v
```

### Using Poetry
```bash
cd src/python
poetry run pytest tests/unittests/
```

### Test with Coverage
```bash
docker-compose -f ../docker/test/python/compose.yml run --rm tests pytest tests/unittests/ --cov=. --cov-report=html
```

## Angular Unit Tests
```bash
cd src/angular
npm test
# or
node_modules/@angular/cli/bin/ng test
```

## E2E Tests
```bash
# Docker image
make run-tests-e2e STAGING_VERSION=latest SEEDSYNC_ARCH=amd64

# Debian package
make run-tests-e2e SEEDSYNC_DEB=`readlink -f build/*.deb` SEEDSYNC_OS=ubu2004
```

## Full Test Suite (Docker)
```bash
make run-tests-python   # Python tests
make run-tests-angular  # Angular tests
make run-tests-e2e      # End-to-end tests
```

---

# Code Quality

## Ruff Linting

```bash
# Check
ruff check .

# Auto-fix
ruff check . --fix
```

Configuration in `pyproject.toml`:
- Target: Python 3.11
- Line length: 120
- Rules: E, F, UP, B, SIM

## Mypy Type Checking

```bash
mypy .
```

Configuration in `pyproject.toml`:
- Python version: 3.11
- Strict optional handling
- Ignore missing imports (for third-party libs)

## Pre-commit Checks

Before committing, ensure:
```bash
cd src/python
ruff check .              # 0 issues
mypy .                    # 0 errors
pytest tests/unittests/   # All pass
```

---

# Build

## Multi-arch Docker Build

1. Setup buildx:
```bash
docker buildx create --name mybuilder --driver docker-container
docker buildx use mybuilder
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
docker buildx inspect --bootstrap
```

2. Start local registry:
```bash
docker run -d -p 5000:5000 --restart=always --name registry registry:2
```

3. Build:
```bash
make clean
make
```

4. Verify:
```bash
curl -X GET http://localhost:5000/v2/_catalog
docker buildx imagetools inspect localhost:5000/seedsync:latest
```

## Custom Registry/Version
```bash
make STAGING_REGISTRY=myregistry:5000 STAGING_VERSION=0.0.1
```

---

# IDE Setup

## PyCharm

1. Set project root to top-level `RapidCopy` directory
2. Configure interpreter to Poetry virtualenv
3. Mark `src/python` as 'Sources Root'
4. Add run configuration:

| Config | Value |
|--------|-------|
| Name | rapidcopy |
| Script path | seedsync.py |
| Parameters | `-c ./build/config --html ../angular/dist --scanfs ./build/scanfs` |

## VS Code

Recommended extensions:
- Python
- Pylance
- Ruff
- Docker

Settings (`.vscode/settings.json`):
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/src/python/.venv/bin/python",
  "python.analysis.typeCheckingMode": "basic",
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff"
  }
}
```

---

# Remote Development Server

For testing, run a mock remote server:

```bash
make run-remote-server
```

Connection parameters:

| Option | Value |
|--------|-------|
| Remote Address | localhost |
| Remote Port | 1234 |
| Username | remoteuser |
| Password | remotepass |
| Remote Path | /home/remoteuser/files |

---

# Release Process

## Using GitHub Actions (Recommended)

1. Update versions:
   - `src/angular/package.json`
   - `src/debian/changelog` (use `LANG=C date -R` for date)
   - `src/e2e/tests/about.page.spec.ts`
   - Copyright in `about-page.component.html`

2. Tag the commit:
```bash
git tag vX.X.X
git push origin vX.X.X
```

GitHub Actions will build and release automatically.

## Manual Release

```bash
make clean && make
make docker-image-release RELEASE_VERSION=X.X.X RELEASE_REGISTRY=your-registry
```

---

# Documentation

## Preview
```bash
cd src/python
poetry run mkdocs serve
```
Preview at [http://localhost:8000](http://localhost:8000)

## Deploy
```bash
poetry run mkdocs gh-deploy
git push github gh-pages
```
