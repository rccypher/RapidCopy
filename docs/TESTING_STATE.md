# RapidCopy Testing State

**Last Updated:** 2026-02-14

## Overview

This document captures the current state of E2E testing migration from Protractor to Playwright, production environment setup, and all discovered issues and fixes.

## Goals

1. Migrate RapidCopy's E2E tests from Protractor (deprecated) to Playwright
2. Perform full breadth testing of the entire application UI
3. Set up a production testing environment with real file transfers between two servers
4. Create comprehensive documentation of all use cases and features
5. Enable backend-dependent Playwright tests, fix Python type errors, add integration tests, and create CI/CD pipeline

## Production Environment

### Servers

| Server | Address | Role | OS |
|--------|---------|------|-----|
| miniplex | 192.168.22.40 | Target server (RapidCopy installed) | Ubuntu 24.04, Docker |
| zucchini | zucchini.whatbox.ca | Source seedbox (pull files FROM) | Whatbox, 21TB storage |

### Access

- SSH config entries exist in `~/.ssh/config` for both servers
- SSH key for zucchini: `/home/jemunos/.ssh/whatbox_key` on miniplex
- Production app runs on port **8800** on miniplex
- SSH tunnel for local testing: `ssh -f -N -L 8801:localhost:8800 miniplex`

### Docker Container

```bash
docker run -d \
  --name rapidcopy \
  --restart unless-stopped \
  -p 8800:8800 \
  -v /home/jemunos/RapidCopy/config:/config \
  -v /home/jemunos/RapidCopy/downloads:/downloads \
  -v /home/jemunos/RapidCopy/ssh:/home/rapidcopy/.ssh:ro \
  rapidcopy:latest
```

### Working Configuration

Location: `/home/jemunos/RapidCopy/config/settings.cfg` on miniplex

```ini
[General]
debug = False
verbose = False
log_level = INFO

[Lftp]
remote_address = zucchini.whatbox.ca
remote_username = jemunos
remote_password = unused-ssh-key-auth
remote_port = 22
remote_path = /home/jemunos/files/complete/sonarr
local_path = /downloads/tv_shows
remote_path_to_scan_script = /tmp
use_ssh_key = True
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
```

**Important:** Do NOT include a `[Validation]` section - it's optional and causes parsing errors if values are `None`.

## Discoveries & Fixes

### 1. WebSocket/SSE Connection Handling

**Issue:** Playwright tests using `networkidle` wait state would hang indefinitely because the app maintains a persistent SSE connection.

**Solution:** Use `domcontentloaded` wait state and wait for `app-root` element instead.

**Commit:** `2ed36f2`

### 2. Backend Availability Check

**Issue:** Tests were using an incorrect endpoint to check backend availability.

**Solution:** Use `/server/config/get` endpoint for backend availability checks.

**Commit:** `4c1cc16`

### 3. Pickle/JSON Format Mismatch in Remote Scanner

**Issue:** The Docker image has an old `scanfs` binary that outputs pickle format, but `remote_scanner.py` was updated to expect JSON only.

**Solution:** Added pickle fallback to `_parse_scan_output()` method in `remote_scanner.py` with appropriate security warnings.

**Commit:** `5d5a90a`

### 4. Missing VALIDATING State in Serialization

**Issue:** The `serialize_model.py` was missing the `VALIDATING` state in its state mapping, causing the SSE stream to crash with `KeyError: <State.VALIDATING: 7>` when trying to serialize files in validating state.

**Solution:** Added `ModelFile.State.VALIDATING: "validating"` to the `__VALUES_FILE_STATE` dictionary.

**Commit:** `5d3e1e8`

### 5. API Path Encoding

**Issue:** Paths with slashes need special encoding for API calls.

**Solution:** Use double URL encoding: `quote(quote('/path', safe=''), safe='')`

### 6. SSH Key Configuration

**Issue:** Container runs as user `rapidcopy` (uid=1000), not root.

**Solution:** SSH keys must be mounted to `/home/rapidcopy/.ssh` (not `/root/.ssh`).

### 7. SSH Config Hostname

**Issue:** SSH config must use full hostname for IdentityFile to work.

**Solution:** Use `Host zucchini.whatbox.ca` (not just an alias) in SSH config.

## Test Commands

### Check Server Status

```bash
# Via SSH tunnel
curl -s "http://127.0.0.1:8801/server/status" | python3 -m json.tool

# Direct access
curl -s "http://192.168.22.40:8800/server/status" | python3 -m json.tool
```

### Check Container Logs

```bash
ssh miniplex "docker logs rapidcopy --tail 30"
```

### Run Playwright Tests

```bash
cd src/e2e-playwright

# Install dependencies (first time)
npm install
npx playwright install chromium

# Run against production (direct - recommended)
RAPIDCOPY_URL=http://192.168.22.40:8800 npx playwright test --project=with-backend --workers=1

# Run against production (via SSH tunnel)
ssh -f -N -L 8801:localhost:8800 miniplex
RAPIDCOPY_URL=http://127.0.0.1:8801 npx playwright test --project=with-backend --workers=1

# Run specific test
RAPIDCOPY_URL=http://192.168.22.40:8800 npx playwright test --project=with-backend -g "should display a list of files"

# Run UI-only tests (no backend required)
npx playwright test --project=chromium
```

### Update Container with Code Changes

```bash
# Quick update (copy file directly)
scp src/python/path/to/file.py miniplex:/tmp/
ssh miniplex "docker cp /tmp/file.py rapidcopy:/app/python/path/to/file.py && docker restart rapidcopy"

# Full rebuild (recommended for major changes)
# Build new image and redeploy
```

## Current Test Status

### Passing Tests

- `should have correct top title @backend` - Dashboard title check
- `should display a list of files @backend` - File list presence (with waitForFileList)
- `should have files with expected structure @backend` - File structure validation

### Tests Requiring Attention

- AutoQueue pattern tests - May need longer timeouts for SSE reconnection
- Action button tests - Depend on file list loading first
- Multi-path feature tests - Depend on path pair configuration

## File Locations

### Local Development

| Path | Description |
|------|-------------|
| `src/e2e-playwright/` | Playwright test directory |
| `src/e2e-playwright/tests/fixtures.ts` | Test fixtures and base page |
| `src/e2e-playwright/tests/pages/*.page.ts` | Page Object classes |
| `src/e2e-playwright/tests/*.spec.ts` | Test specifications |
| `src/python/controller/scan/remote_scanner.py` | Remote scanner (pickle fix) |
| `src/python/web/serialize/serialize_model.py` | Model serialization (VALIDATING fix) |

### Production Server (miniplex)

| Path | Description |
|------|-------------|
| `/home/jemunos/RapidCopy/` | RapidCopy installation |
| `/home/jemunos/RapidCopy/config/settings.cfg` | Configuration file |
| `/home/jemunos/RapidCopy/ssh/` | SSH config and keys for container |
| `/home/jemunos/RapidCopy/downloads/tv_shows/` | Download directory |

## Known Issues

1. **SSE Stream Closes Quickly:** The Bottle/PasteWSGI server uses HTTP/1.0 which causes `Connection: close` behavior. The Angular app handles reconnection, but tests may need to wait for files to load.

2. **Repeated Auto-Queue Messages:** Logs show the same file being auto-queued repeatedly. This may indicate a bug in the controller loop (separate from E2E testing).

3. **SSH Tunnel SSE Issues:** SSE streaming through SSH tunnel may be unreliable. Recommend using direct IP access (192.168.22.40:8800) for tests.

## Git Commits (Recent)

| Commit | Description |
|--------|-------------|
| `5d3e1e8` | fix: add VALIDATING state to model serialization |
| `5d5a90a` | fix: add pickle fallback to remote_scanner for legacy scanfs binaries |
| `4c1cc16` | fix: use /server/config/get for backend availability checks |
| `2ed36f2` | fix: resolve Playwright test stability issues with WebSocket-based app |
| `5df693d` | feat: enable backend-dependent Playwright tests and add CI/CD pipeline |

## Next Steps

1. Run full Playwright test suite against production
2. Fix any remaining test failures
3. Document all test cases and expected behaviors
4. Set up CI/CD pipeline to run tests automatically
5. Consider updating scanfs binary to output JSON instead of pickle
