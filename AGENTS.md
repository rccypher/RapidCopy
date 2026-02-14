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
