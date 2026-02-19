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
- **Production volume mounts**:
  - `/mnt/media/TV_Downloads` → `/downloads/tv_shows`
  - `/mnt/MediaVaultV3/Movie_Downloads` → `/downloads/movies`
  - `~/.ssh` → `/home/rapidcopy/.ssh` (read-only)

### Dev Machine: local Mac (jemunos)

- **Working directory**: `~/Documents/projects/RapidCopy/`
- Same git repo, synced via push/pull
- Claude Code runs here and SSHes to miniplex for builds/tests

---

## Pending Work

### Active To-Dos

| # | Task | Priority | Est. Effort | Status |
|---|------|----------|-------------|--------|
| 1 | Log file persistence + UI text search | HIGH | ~40-50% session | Pending |
| 2 | Close GitHub issue #1 (inline validation done — just needs closing) | LOW | 5 min | Blocked — needs GH PAT |
| 3 | Publish Docker image to Docker Hub | MEDIUM | ~1 session | Pending |
| 4 | Add validation settings to Settings UI | MEDIUM | ~20-30% session | Pending |
| 5 | Add pre-bundled RAR test fixtures (fix integration tests) | MEDIUM | ~2 hrs | Pending |
| 6 | Update MODERNIZATION-PLAN.md to reflect current state | LOW | 15 min | Pending |
| 7 | Fix 6 pre-existing unit test failures (config/validation/scanner) | MEDIUM | ~1-2 hrs | Pending |

### Completed This Session (Feb 18–19 2026)

- **Housekeeping**: Committed `docker-compose.yml` with correct production volume mounts
- **Deprecation warnings**: Fixed `SyntaxWarning: invalid escape sequence` in `test_job_status_parser.py`
- **Git remote**: Switched to SSH (`git@github.com:rccypher/RapidCopy.git`)
- **Dep pinning (Task 6)**: `poetry update` — updated 32 packages, removed 10 stale deps (waitress 1.4→3.0, requests 2.25→2.32, urllib3 1.26→2.6, etc.). 437 tests pass.
- **Inline validation (Task 2)**: Implemented `validate_after_chunk` — chunks are now hashed as they arrive during download. Wire-up in `ValidationDispatch`, `ValidationProcess`, and `Controller`. No new test failures.
- **Corrupt chunk re-download (arch fix)**: Removed broken `validate_after_file` post-download path. Corrupt retryable chunks now trigger `Lftp.pget_range()` (new method) to re-fetch only that byte range. `ValidationDispatch` marks chunk as `DOWNLOADING` and emits `CorruptChunkRedownload`; controller issues `pget --range`, polls `os.path.getsize()`, then calls `resume_chunk()` to re-hash. `validate_after_chunk` defaults to `True`. 437 tests still pass.
- **Build fix**: Added `.ruff_cache` and `.mypy_cache` to `.dockerignore` (were root-owned by docker test runs, blocked `docker build` context).
- **pget_range bug fix (prod)**: Found via production logs — `queue '...'` wrapper on `pget_range` caused `LftpJobStatusParser` errors when corrupt chunks were being re-downloaded. Fixed by running `pget --range` directly (no `queue` wrapper) and dropping `-c` (continue) flag. Verified clean in production logs + 150/150 Playwright tests pass.

### Session Capacity Notes

- **Task 1 (log persistence)**: Large — fills a full session on its own.
- **Task 5 (RAR fixtures)**: Self-contained standalone session task (~2 hrs).
- **Task 7 (pre-existing test failures)**: Good warm-up task; failures are in `test_config.py` (missing `General.log_level`, `Lftp.rate_limit` keys), `test_rapidcopy.py` (uninitialized `Validation.enabled`), and `test_remote_scanner.py` (stale error message string). All are application-level, not dep-related.
