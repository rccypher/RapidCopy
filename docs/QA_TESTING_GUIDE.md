# RapidCopy QA Testing Guide

This guide covers how to set up a complete QA testing environment for RapidCopy, including all features: file synchronization, network mounts, auto-update, and more.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Environment Overview](#environment-overview)
3. [Setup Options](#setup-options)
4. [Test Credentials](#test-credentials)
5. [Feature Test Checklist](#feature-test-checklist)
6. [Running Automated Tests](#running-automated-tests)
7. [Manual Testing Guide](#manual-testing-guide)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

```bash
# Start the full QA environment
docker-compose -f docker-compose.qa.yml up --build

# Access RapidCopy UI
open http://localhost:8800

# Run automated E2E tests
docker-compose -f docker-compose.qa.yml --profile testing run playwright
```

---

## Environment Overview

The QA environment consists of multiple services:

| Service | Purpose | Port | Container Name |
|---------|---------|------|----------------|
| `rapidcopy` | Main application (backend + UI) | 8800 | rapidcopy-qa |
| `remote` | Mock SSH server (seedbox simulator) | 1234 | rapidcopy-qa-remote |
| `nfs-server` | NFS share for mount testing | 2049 | rapidcopy-qa-nfs |
| `smb-server` | SMB/CIFS share for mount testing | 445, 139 | rapidcopy-qa-smb |
| `configure` | Auto-configures RapidCopy | - | rapidcopy-qa-configure |
| `playwright` | Automated E2E test runner | - | rapidcopy-qa-playwright |

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     QA Test Environment                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐     SSH (1234)     ┌──────────────────┐       │
│  │              │◄───────────────────│                  │       │
│  │   RapidCopy  │                    │   Remote SSH     │       │
│  │   (8800)     │                    │   (seedbox)      │       │
│  │              │                    │                  │       │
│  └──────┬───────┘                    └──────────────────┘       │
│         │                                                        │
│         │ mount                                                  │
│         ▼                                                        │
│  ┌──────────────┐                    ┌──────────────────┐       │
│  │              │     NFS (2049)     │                  │       │
│  │   /mounts    │◄───────────────────│   NFS Server     │       │
│  │              │                    │                  │       │
│  │              │     SMB (445)      ├──────────────────┤       │
│  │              │◄───────────────────│   SMB Server     │       │
│  └──────────────┘                    └──────────────────┘       │
│                                                                  │
│  ┌──────────────┐                                               │
│  │  Playwright  │────────────────────► Browser Tests            │
│  │  (optional)  │                                               │
│  └──────────────┘                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Setup Options

### Option A: Full Docker Environment (Recommended)

Best for: Complete isolation, consistent results, CI/CD pipelines

```bash
# Build and start all services
docker-compose -f docker-compose.qa.yml up --build -d

# View logs
docker-compose -f docker-compose.qa.yml logs -f rapidcopy

# Stop environment
docker-compose -f docker-compose.qa.yml down

# Clean up volumes (full reset)
docker-compose -f docker-compose.qa.yml down -v
```

### Option B: Local Development + Docker Services

Best for: Debugging, iterative development

```bash
# 1. Start only the support services
docker-compose -f docker-compose.qa.yml up -d remote nfs-server smb-server

# 2. Run RapidCopy locally
cd src/python
poetry install
poetry run python rapidcopy.py -c ../../config --html ../angular/dist/angular/browser

# 3. Or run Angular dev server separately
cd src/angular
npm install
npm run start  # http://localhost:4200
```

### Option C: Minimal Setup (UI Testing Only)

Best for: Quick UI checks, no backend features

```bash
# Just run Angular dev server
cd src/angular
npm install
npm run start

# Run Playwright tests against dev server
cd src/e2e-playwright
RAPIDCOPY_URL=http://localhost:4200 npx playwright test
```

---

## Test Credentials

### Remote SSH Server (Seedbox Simulator)

| Field | Value |
|-------|-------|
| Host | `remote` (in Docker) or `localhost` (external) |
| Port | `1234` |
| Username | `remoteuser` |
| Password | `remotepass` |
| Remote Path | `/home/remoteuser/files` |

### NFS Server

| Field | Value |
|-------|-------|
| Server | `nfs-server` (in Docker) or `localhost` (external) |
| Export Path | `/data` |
| Mount Options | `vers=4,rw` |

### SMB/CIFS Server

**Public Share (Guest Access):**

| Field | Value |
|-------|-------|
| Server | `smb-server` (in Docker) or `localhost` (external) |
| Share Name | `public` |
| Username | (leave empty) |
| Password | (leave empty) |

**Private Share (Authenticated):**

| Field | Value |
|-------|-------|
| Server | `smb-server` (in Docker) or `localhost` (external) |
| Share Name | `private` |
| Username | `smbuser` |
| Password | `smbpass` |

---

## Feature Test Checklist

### Dashboard Features

- [ ] File list displays remote files
- [ ] Filter searchbox filters files by name
- [ ] Status dropdown filters by status (All, Queued, Downloading, Downloaded, etc.)
- [ ] Sort dropdown changes sort order
- [ ] Details toggle shows/hides file details
- [ ] Queue/Stop/Delete actions work on files
- [ ] Download progress updates in real-time
- [ ] ETA and speed display correctly

### Settings - Server Configuration

- [ ] Server Address field saves correctly
- [ ] Server User/Password authentication works
- [ ] SSH key authentication works (mount key to container)
- [ ] Remote SSH Port configuration works
- [ ] Server Script Path is configurable
- [ ] Connection test succeeds with valid credentials

### Settings - Path Pairs

- [ ] Add new path pair with name, remote path, local path
- [ ] Edit existing path pair
- [ ] Delete path pair
- [ ] Enable/disable path pair toggle
- [ ] AutoQueue toggle per path pair
- [ ] Validation errors show for invalid paths

### Settings - Network Mounts

- [ ] Add NFS mount with server and export path
- [ ] Add SMB/CIFS mount with server, share, credentials
- [ ] Mount type dropdown switches between NFS/SMB
- [ ] Credentials section shows/hides based on mount type
- [ ] Enable/disable mount toggle
- [ ] Mount/unmount actions work
- [ ] Mount status indicator updates
- [ ] Delete network mount

### Settings - Connections

- [ ] Max Parallel Downloads setting saves
- [ ] Max Total Connections setting saves
- [ ] Download Rate Limit setting saves (e.g., "1M", "500K", "0")
- [ ] Per-file connection settings save
- [ ] Rename unfinished files toggle works

### Settings - AutoQueue

- [ ] Enable AutoQueue toggle works
- [ ] Restrict to patterns toggle works
- [ ] Auto extraction toggle works

### Settings - Archive Extraction

- [ ] Extract in downloads directory toggle
- [ ] Custom extract path configuration

### Settings - File Discovery

- [ ] Remote scan interval configurable
- [ ] Local scan interval configurable
- [ ] Downloading scan interval configurable

### Settings - Other

- [ ] Web GUI Port configurable (requires restart)
- [ ] Enable Debug toggle
- [ ] Log Level dropdown (DEBUG, INFO, WARNING, ERROR, CRITICAL)

### AutoQueue Page

- [ ] View existing patterns
- [ ] Add new pattern with "+" button
- [ ] Delete pattern
- [ ] Pattern matching works for file downloads

### Logs Page

- [ ] Log entries display
- [ ] Logs update in real-time
- [ ] Log level filtering (if implemented)

### About Page

- [ ] Version number displays correctly
- [ ] GitHub link works
- [ ] Flaticon attribution link works
- [ ] Auto-update status shows (configured/not configured)
- [ ] Update button works (when update server is running)

### General UI

- [ ] Dark mode toggle works
- [ ] Dark mode persists across page navigation
- [ ] Restart button shows confirmation
- [ ] Lost connection banner shows when backend is down
- [ ] All navigation links work

---

## Running Automated Tests

### Playwright E2E Tests

```bash
# Run all tests (headless)
cd src/e2e-playwright
npm install
npx playwright install chromium
npx playwright test

# Run against QA environment
RAPIDCOPY_URL=http://localhost:8800 npx playwright test

# Run in headed mode (see browser)
npx playwright test --headed

# Run specific test file
npx playwright test tests/settings.spec.ts

# Run with debug mode
npx playwright test --debug

# Generate HTML report
npx playwright test --reporter=html
npx playwright show-report
```

### Using Docker Playwright Runner

```bash
# Start QA environment with test runner
docker-compose -f docker-compose.qa.yml --profile testing up --build

# Or run tests separately
docker-compose -f docker-compose.qa.yml --profile testing run playwright

# View test results
ls src/e2e-playwright/test-results/
ls src/e2e-playwright/playwright-report/
```

### Test Tags

Tests are tagged to indicate their requirements:

| Tag | Description | Requires |
|-----|-------------|----------|
| `@ui-only` | Pure frontend tests | Nothing (Angular dev server OK) |
| `@backend` | Needs Python backend | Backend running |
| `@remote` | Needs file transfers | Backend + Remote SSH |
| `@mounts` | Needs mount operations | Backend + NFS/SMB + privileges |

Run tests by tag:

```bash
# UI-only tests (no backend needed)
npx playwright test --grep "@ui-only"

# Skip backend-dependent tests
npx playwright test --grep-invert "@backend"
```

---

## Manual Testing Guide

### Test Scenario 1: Basic File Download

1. Start QA environment: `docker-compose -f docker-compose.qa.yml up`
2. Open http://localhost:8800
3. Navigate to Dashboard
4. Verify remote files appear (clients.jpg, testing.gif, etc.)
5. Click a file to queue it
6. Verify download starts and progress updates
7. Verify file appears in `/downloads` when complete

### Test Scenario 2: Path Pair Configuration

1. Navigate to Settings
2. Click "+ Add Path Pair"
3. Enter: Name="Test Pair", Remote="/home/remoteuser/files/goose", Local="/downloads/goose"
4. Save and verify pair appears in list
5. Verify remote files from that path appear on Dashboard
6. Test enable/disable toggle
7. Delete the path pair

### Test Scenario 3: NFS Mount

1. Navigate to Settings > Network Mounts
2. Click "+ Add Network Mount"
3. Select Type: NFS
4. Enter: Name="Test NFS", Server="nfs-server", Share Path="/data"
5. Save and verify mount appears
6. Click "Mount" action
7. Verify mount status shows "Mounted"
8. Create a path pair using `/mounts/test-nfs` as local path
9. Download a file and verify it appears on the NFS share

### Test Scenario 4: SMB Mount with Authentication

1. Navigate to Settings > Network Mounts
2. Click "+ Add Network Mount"
3. Select Type: SMB/CIFS
4. Enter: Name="Private SMB", Server="smb-server", Share="private"
5. Enter credentials: Username="smbuser", Password="smbpass"
6. Save and mount
7. Verify mount succeeds with authentication

### Test Scenario 5: Dark Mode Persistence

1. Toggle Dark Mode on
2. Refresh the page
3. Verify dark mode is still active
4. Navigate to each page
5. Verify dark mode persists

---

## Troubleshooting

### RapidCopy Can't Connect to Remote Server

```bash
# Check remote server is running
docker ps | grep rapidcopy-qa-remote

# Test SSH connection manually
docker exec -it rapidcopy-qa ssh -p 1234 remoteuser@remote

# Check logs
docker logs rapidcopy-qa-remote
```

### Network Mount Fails

```bash
# Check NFS server
docker logs rapidcopy-qa-nfs

# Check if RapidCopy has mount privileges
docker exec -it rapidcopy-qa mount

# Manual NFS mount test
docker exec -it rapidcopy-qa mount -t nfs nfs-server:/data /mnt/test
```

### Playwright Tests Fail

```bash
# Run with trace for debugging
npx playwright test --trace on

# View trace
npx playwright show-trace test-results/*/trace.zip

# Run single test with debug
npx playwright test tests/dashboard.spec.ts --debug
```

### Container Won't Start

```bash
# Check for port conflicts
lsof -i :8800
lsof -i :1234

# Full cleanup and restart
docker-compose -f docker-compose.qa.yml down -v
docker system prune -f
docker-compose -f docker-compose.qa.yml up --build
```

### Configuration Not Persisting

```bash
# Check volume mounts
docker volume ls | grep rapidcopy

# Inspect config volume
docker run --rm -v rapidcopy-qa_rapidcopy-config:/config alpine ls -la /config

# Reset configuration
docker-compose -f docker-compose.qa.yml down -v
```

---

## Appendix: Test Files on Remote Server

The mock remote server includes these test files:

| File | Size | Purpose |
|------|------|---------|
| `clients.jpg` | 37KB | Small image download |
| `illusion.jpg` | 83KB | Medium image download |
| `documentation.png` | 9KB | Small image download |
| `testing.gif` | 9.4MB | Large file download |
| `áßç déÀ.mp4` | 860KB | Unicode filename handling |
| `crispycat/` | Directory | Directory sync test |
| `goose/` | Directory | Directory sync test |
| `joke/` | Directory | Directory sync test |
| `üæÒ/` | Directory | Unicode directory name |

---

## Appendix: Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RAPIDCOPY_URL` | `http://localhost:8800` | URL for Playwright tests |
| `UPDATE_TOKEN` | `qa-test-token-12345` | Token for auto-update feature |
| `UPDATE_SERVER_URL` | `http://host.docker.internal:8801` | Update server endpoint |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-02-14 | Initial QA guide with docker-compose.qa.yml |
