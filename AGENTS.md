# AGENTS.md - AI Agent Instructions for RapidCopy

RapidCopy is a fast file synchronization tool from remote Linux servers using LFTP.

## Tech Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Backend   | Python     | 3.11+   |
| Frontend  | Angular    | 18.2    |
| Linting   | Ruff       | 0.4+    |
| Types     | Mypy       | 1.10+   |
| Testing   | Pytest     | 8.0+    |
| E2E       | Playwright | 1.52+   |

## Build/Lint/Test Commands

### Python (from `src/python/`)

```bash
# Run all unit tests
poetry run pytest tests/unittests/ -v

# Single test file
poetry run pytest tests/unittests/test_rapidcopy.py -v

# Single test method
poetry run pytest tests/unittests/test_rapidcopy.py::TestRapidcopy::test_args_config -v

# Tests matching pattern
poetry run pytest tests/unittests/ -k "test_args" -v

# Lint (must be 0 issues)
ruff check .

# Auto-fix lint issues
ruff check . --fix

# Type check (must be 0 errors)
mypy .
```

### Angular (from `src/angular/`)

```bash
# Run all tests (watch mode)
npm test

# Headless (CI mode)
npm test -- --no-watch --browsers=ChromeHeadless

# Single test file
npm test -- --include=src/app/tests/unittests/services/path-pair.service.spec.ts
```

### E2E Tests (Playwright)

Located in `src/e2e-playwright/`

```bash
cd src/e2e-playwright

# Install dependencies
npm install

# Install browsers (first time only)
npx playwright install chromium

# Run all tests (headless) - UI-only tests, no backend required
npx playwright test

# Run against Angular dev server (port 4200)
RAPIDCOPY_URL=http://localhost:4200 npx playwright test

# Run with UI (headed mode)
npx playwright test --headed

# Run specific test file
npx playwright test tests/dashboard.spec.ts

# Run with debug mode
npx playwright test --debug

# Generate HTML report
npx playwright test --reporter=html
npx playwright show-report
```

**Makefile Targets:**
```bash
# Run from project root
make run-tests-e2e-playwright        # Headless against production (port 8800)
make run-tests-e2e-playwright-headed # Headed mode
make run-tests-e2e-playwright-dev    # Against Angular dev server (port 4200)
make run-tests-e2e-playwright-report # Generate HTML report
```

**Test Structure:**
- `tests/fixtures.ts` - Base test fixtures
- `tests/pages/*.page.ts` - Page Object classes
- `tests/*.spec.ts` - Test specifications

**Test Tags:**
- Tests tagged `@backend` require the Python backend to be running
- UI-only tests run without backend (most tests pass in this mode)

**Available Page Objects:**
- `DashboardPage` - File list, filters, status (requires backend)
- `SettingsPage` - Server config, path pairs, network mounts
- `AutoQueuePage` - Pattern management
- `LogsPage` - Log viewer
- `AboutPage` - Version info

### Legacy E2E Tests (Protractor - Deprecated)

```bash
# Debian package
make run-tests-e2e RAPIDCOPY_DEB=/path/to/rapidcopy.deb RAPIDCOPY_OS=ubu2004

# Docker image
make run-tests-e2e STAGING_REGISTRY=localhost:5000 STAGING_VERSION=latest RAPIDCOPY_ARCH=amd64
```

### Pre-commit Checklist

```bash
cd src/python
ruff check .                         # 0 issues
mypy .                               # 0 errors
poetry run pytest tests/unittests/   # All pass
```

## Python Code Style

### Imports

Order: stdlib → third-party → local (with `# my libs` comment)

### Formatting

- **Line length**: 120 chars
- **Indentation**: 4 spaces
- **Type hints**: Modern syntax (`list[str]`, `X | None`)
- **Naming**: `snake_case` functions/vars, `PascalCase` classes, `UPPER_SNAKE_CASE` constants

### Error Handling

- **Delay exceptions in constructors** - wait until web service is up so users see errors in UI
- Custom exceptions extend `AppError`

### Constructor Guidelines

- Keep constructors short and passive
- Don't start threads/processes in constructors

### Test Guidelines

- Never use `time.sleep()` - use condition checks with watchdog timers
- Test classes: `Test*` prefix, methods: `test_*` prefix

### Ruff Rules

Enabled: `E` (pycodestyle), `F` (pyflakes), `UP` (pyupgrade), `B` (bugbear), `SIM` (simplify)

## Angular/TypeScript Code Style

- **Indentation**: 2 spaces
- **Quotes**: Single quotes

### Immutable.js Records

Do NOT declare class fields (they shadow getters):

```typescript
// WRONG
class ViewFile extends ViewFileRecord {
    name: string;  // Shadows getter!
}

// CORRECT
class ViewFile extends ViewFileRecord {
    get name(): string { return this.get("name"); }
}
```

### RxJS 7

- Use `new Observable().pipe()` not `Observable.create()`
- Import from `rxjs`: `import { of, throwError } from 'rxjs'`

### Angular DI

Test services extending `@Injectable()` parent must also have `@Injectable()` decorator.

## Project Structure

```
src/
├── python/           # Python backend
│   ├── rapidcopy.py  # Entry point
│   ├── common/       # Config, persistence, utilities
│   ├── controller/   # Business logic
│   ├── web/          # REST API handlers
│   └── tests/        # Unit & integration tests
├── angular/          # Frontend (src/app/)
├── e2e/              # Legacy Protractor E2E tests (deprecated)
├── e2e-playwright/   # Playwright E2E tests
└── docker/           # Docker configs
```

## Key Patterns

- **Dataclasses**: Use `@dataclass` with `__post_init__` for validation
- **Persistence**: Extend `Persist` for JSON serialization; use manager classes for CRUD + file I/O
- **Custom errors**: Extend `AppError` (e.g., `PathPairError`, `ConfigError`)

---

## Build Environment

### Primary Build Host: miniplex

All builds, tests, and git operations run on **miniplex** (`ssh miniplex`). This machine is on the local network and resolves via mDNS/hosts as `miniplex.oysterbay.home`.

- **Working directory**: `~/RapidCopy/`
- **Python version on host**: 3.12.3 (Docker builds use Python 3.11-slim)
- **Git remote**: `git@github.com:rccypher/RapidCopy.git` (SSH)
- **GitHub access**: SSH key auth works (`ssh -T git@github.com`). No `gh` CLI installed. Use `curl` + GitHub REST API for issue management. No stored API token — GH API writes (closing issues, etc.) require a PAT provided at runtime.
- **Production container**: Running at `http://miniplex:8800`
- **Config location**: `/home/jemunos/rapidcopy-config/` (persists across rebuilds)
  - `settings.cfg` — main config (server address, credentials, etc.)
  - `path_pairs.json` — source/destination path mappings
  - `backups/` — auto-backups created before every config/path-pairs write (10-file rotation)
- **Correct `docker run` command** (must use exact paths):
  ```
  docker run -d --name rapidcopy --restart unless-stopped \
    -v /mnt/media:/mnt/media \
    -v /home/jemunos/rapidcopy-config:/config \
    -v /home/jemunos/.ssh/whatbox_key:/home/rapidcopy/.ssh/id_rsa:ro \
    -p 8800:8800 rapidcopy
  ```
- **WARNING**: Do NOT mount to `/root/.config/rapidcopy` — the container runs as uid 1000 (`rapidcopy`), not root. The config dir inside the container is `/config`.
- **Production volume mounts** (media only):
  - `/mnt/media` → `/mnt/media` (TV downloads land in `/mnt/media/TV_Downloads`)

### Dev Machine: local Mac (jemunos)

- **Working directory**: `~/Documents/projects/RapidCopy/`
- Same git repo, synced via push/pull
- Claude Code runs here and SSHes to miniplex for builds/tests

---

## Pending Work

### Active To-Dos

| # | Task | Priority | Est. Effort | Status |
|---|------|----------|-------------|--------|
| 2 | Close GitHub issue #1 (inline validation done — just needs closing) | LOW | 5 min | Blocked — needs GH PAT |
| 3 | Publish Docker image to Docker Hub | MEDIUM | ~1 session | Pending |

### Completed This Session (Feb 19 2026 — continued)

- **Housekeeping**: Committed `docker-compose.yml` with correct production volume mounts
- **Deprecation warnings**: Fixed `SyntaxWarning: invalid escape sequence` in `test_job_status_parser.py`
- **Git remote**: Switched to SSH (`git@github.com:rccypher/RapidCopy.git`)
- **Dep pinning (Task 6)**: `poetry update` — updated 32 packages, removed 10 stale deps (waitress 1.4→3.0, requests 2.25→2.32, urllib3 1.26→2.6, etc.). 437 tests pass.
- **Inline validation (Task 2)**: Implemented `validate_after_chunk` — chunks are now hashed as they arrive during download. Wire-up in `ValidationDispatch`, `ValidationProcess`, and `Controller`. No new test failures.
- **Corrupt chunk re-download (arch fix)**: Removed broken `validate_after_file` post-download path. Corrupt retryable chunks now trigger `Lftp.pget_range()` (new method) to re-fetch only that byte range. `ValidationDispatch` marks chunk as `DOWNLOADING` and emits `CorruptChunkRedownload`; controller issues `pget --range`, polls `os.path.getsize()`, then calls `resume_chunk()` to re-hash. `validate_after_chunk` defaults to `True`. 437 tests still pass.
- **Build fix**: Added `.ruff_cache` and `.mypy_cache` to `.dockerignore` (were root-owned by docker test runs, blocked `docker build` context).
- **pget_range bug fix (prod)**: Found via production logs — `queue '...'` wrapper on `pget_range` caused `LftpJobStatusParser` errors when corrupt chunks were being re-downloaded. Fixed by running `pget --range` directly (no `queue` wrapper) and dropping `-c` (continue) flag. Verified clean in production logs + 150/150 Playwright tests pass.
- **Task 8 — Checkbox alignment**: Replaced Bootstrap `.form-check` div+label structure with a plain `<label>` wrapping the checkbox input; custom flex SCSS. Checkbox now sits inline with its label, description wraps below.
- **Config persistence fix**: Discovered container ran as uid 1000 (`rapidcopy`), config mount was `/root/.config/rapidcopy` (wrong). Established `/home/jemunos/rapidcopy-config:/config` as the canonical persistent config location. Recovered config from backup. Fixed `path_pairs.json` paths. Added `/mnt/MediaVaultV3` volume mount for Movies path pair.
- **Auto-backup on write (Tasks 6/8/config)**: `rapidcopy.py.__backup_file()` now creates timestamped backups in `backups/` subdir with 10-file rotation. Called in `persist()` before every `settings.cfg` write. Same logic added to `path_pair.py save()` for `path_pairs.json`.
- **Task 6 — MODERNIZATION-PLAN.md**: Marked done (AGENTS.md updated to reflect current state).
- **Task 9 — Dashboard download percentages**: Marked done (resolved in prior session).
- **Task 1 — Log file persistence + UI text search**: Full end-to-end implementation. Backend: `--logdir /logs` in Dockerfile CMD, `/logs` dir owned by `rapidcopy`, `stream_log.py` cache 3s→30s, new `GET /server/logs` endpoint (`logs.py`) reads rotating log files with search/level/limit/before params. Frontend: new `LogQueryService`, rewritten `logs-page.component.ts` with debounced `switchMap` search pipeline, search toolbar (text input + level select + clear button + status), conditional live-stream vs search-results display. 151 Playwright tests pass.
- **Task 7 — Unit test failures**: Updated `test_config.py` to include `log_level` in `General` good_dict and `rate_limit` in `Lftp` good_dict; fixed `check_common` to exclude null-checked fields from empty-value assertion; updated `test_to_file` golden string to include `[Validation]` section and new fields. Updated `rapidcopy.py._create_default_config()` to initialize all Validation fields. Fixed `test_remote_scanner.py` stale error message (`"Invalid pickled data"` → `"Invalid scan data format"`). 38/38 unit tests pass.
- **Task 4 — Validation settings UI**: Added `OPTIONS_CONTEXT_VALIDATION` to `options-list.ts` with 8 options (enabled checkbox, algorithm text, chunk sizes, retries, adaptive sizing). Wired into `settings-page.component.ts` and `settings-page.component.html` (left column, after Archive Extraction).
- **Task 5 — RAR test fixtures**: Generated `file.rar`, `file.split.part1.rar`, `file.split.part2.rar` via Docker Ubuntu 22.04 with `rar` installed. Stored in `tests/integration/test_controller/test_extract/fixtures/`. Updated `test_extract.py` to copy fixtures from disk instead of calling `rar` CLI. All 18 extract integration tests pass.
