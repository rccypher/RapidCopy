# RapidCopy Full Modernization Plan

**Version**: 2.0  
**Date**: February 2026  
**Author**: Claude (AI-Assisted Development)  
**Status**: Active Development

---

## Executive Summary

This document provides a complete modernization roadmap for RapidCopy, a file synchronization application built on Python + Angular. The plan addresses critical security vulnerabilities, technical debt, and positions the application for long-term maintainability.

### Current State (February 2026)

| Component | Current | Target | Status |
|-----------|---------|--------|--------|
| Python | 3.11 | 3.12+ | **DONE** (upgraded from 3.8) |
| Angular | 4.2.4 | 18.x | Pending |
| RxJS | 5.4.2 | 7.x | Pending |
| TypeScript | 3.2.2 | 5.x | Pending |
| Node.js | 8.x | 22 LTS | Pending |

### Completed Work

- Python 3.8 → 3.11 upgrade
- Poetry 2.x migration
- Bottle dependency fix (getargspec compatibility)
- Test Dockerfile modernization (Debian Trixie)
- Unit tests passing (404/408)

---

## Table of Contents

1. [Modernization Philosophy](#modernization-philosophy)
2. [Phase 1: Foundation (Weeks 1-2)](#phase-1-foundation)
3. [Phase 2: Python Hardening (Weeks 3-4)](#phase-2-python-hardening)
4. [Phase 3: Angular Migration Path (Weeks 5-12)](#phase-3-angular-migration-path)
5. [Phase 4: Testing Modernization (Weeks 13-14)](#phase-4-testing-modernization)
6. [Phase 5: Infrastructure (Weeks 15-16)](#phase-5-infrastructure)
7. [Phase 6: Quality & Documentation (Weeks 17-18)](#phase-6-quality--documentation)
8. [Phase 7: Optional Enhancements (Weeks 19-24)](#phase-7-optional-enhancements)
9. [Risk Management](#risk-management)
10. [Success Metrics](#success-metrics)

---

## Modernization Philosophy

### Guiding Principles

1. **Incremental Migration** - Never skip major versions; each upgrade should be testable
2. **Test-First** - Every change must pass existing tests before proceeding
3. **Zero Downtime** - Docker images should remain buildable throughout
4. **Security First** - Address CVEs before features
5. **Documentation as Code** - Update docs with every significant change

### Migration Strategy

```
[Current State]                    [Target State]
     |                                   |
     v                                   v
Python 3.8 -----> 3.11 -----> 3.12+ (Latest)
Angular 4 --> 6 --> 9 --> 12 --> 15 --> 18
RxJS 5 -----> 6 -----> 7 (Latest)
Node 8 ----> 18 ----> 20 ----> 22 (LTS)
```

---

## Phase 1: Foundation

**Duration**: Weeks 1-2 (CURRENT PHASE)  
**Status**: 80% Complete  
**Goal**: Stabilize Python backend on modern runtime

### 1.1 Python 3.11 Upgrade ✅ COMPLETE

| Task | Status | Files Changed |
|------|--------|---------------|
| Update base Docker image to Python 3.11-slim | ✅ | `src/docker/build/docker-image/Dockerfile` |
| Poetry 2.x CLI syntax | ✅ | `src/docker/build/docker-image/Dockerfile` |
| Fix bottle dependency (>=0.12.25) | ✅ | `src/python/pyproject.toml` |
| Update pytest to ^8.0 | ✅ | `src/python/pyproject.toml` |
| Regenerate poetry.lock | ✅ | `src/python/poetry.lock` |
| Fix test Dockerfile (unrar, mkdir -p) | ✅ | `src/docker/test/python/Dockerfile` |

### 1.2 Remaining Foundation Tasks

| Task | Priority | Effort | Notes |
|------|----------|--------|-------|
| Commit Python 3.11 changes | HIGH | 15 min | Current uncommitted work |
| Update DEB build Dockerfile | HIGH | 2 hrs | Still uses Python 3.8 + Ubuntu 16.04 |
| Pin all Python dependencies | HIGH | 1 hr | Replace `*` with version ranges |
| Add pre-bundled RAR test fixtures | MEDIUM | 2 hrs | Fix integration tests |
| Document deprecation warnings | LOW | 1 hr | Invalid escape sequences in regex |

### 1.3 Dependency Pinning

Current state (wildcards everywhere):
```toml
bottle = "*"
mkdocs = "*"
requests = "*"
```

Target state (explicit versions):
```toml
[tool.poetry.dependencies]
python = "^3.11"
bottle = "^0.13.4"
mkdocs = "^1.6.0"
mkdocs-material = "^9.5.0"
parameterized = "^0.9.0"
paste = "^3.10.1"
patool = "^3.0.1"
pexpect = "^4.9.0"
pytz = "^2024.2"  # Consider replacing with zoneinfo
requests = "^2.32.0"
tblib = "^3.0.0"
timeout-decorator = "^0.5.0"

[tool.poetry.group.dev.dependencies]
pyinstaller = "^6.10.0"
testfixtures = "^8.3.0"
webtest = "^3.0.0"
pytest = "^8.3.0"
pytest-cov = "^5.0.0"  # NEW: coverage reporting
mypy = "^1.11.0"       # NEW: type checking
ruff = "^0.6.0"        # NEW: linting
```

---

## Phase 2: Python Hardening

**Duration**: Weeks 3-4  
**Goal**: Production-ready Python backend with modern tooling

### 2.1 Type Hints (Target: 90% Coverage)

Current coverage: ~32%  
Target coverage: 90%

**Files requiring type hints** (prioritized):

| Module | Files | Complexity | Priority |
|--------|-------|------------|----------|
| `common/` | 8 files | Medium | HIGH |
| `model/` | 4 files | Low | HIGH |
| `controller/` | 12 files | High | MEDIUM |
| `web/` | 15 files | Medium | MEDIUM |
| `lftp/` | 4 files | High | MEDIUM |
| `ssh/` | 2 files | Low | LOW |
| `system/` | 3 files | Low | LOW |

**Example transformation**:

Before:
```python
def _load_persist(cls, file_path):
    with open(file_path, 'r') as f:
        return cls.from_str(f.read())
```

After:
```python
from typing import TypeVar

T = TypeVar('T', bound='Persist')

def _load_persist(cls: type[T], file_path: str) -> T:
    """Load a persist object from file.
    
    Args:
        cls: The Persist subclass to instantiate
        file_path: Path to the persist file
        
    Returns:
        Instance of the persist class
        
    Raises:
        PersistError: If file cannot be read or parsed
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return cls.from_str(f.read())
```

### 2.2 Fix Deprecation Warnings

Current warnings (78 in test run):
- `DeprecationWarning: invalid escape sequence '\d'` (and similar)
- Location: `lftp/job_status_parser.py` (50+ occurrences)
- Location: `controller/extract/dispatch.py`
- Location: `system/scanner.py`

**Fix**: Convert regular string to raw string:

```python
# Before
pattern = "^\d+\."

# After
pattern = r"^\d+\."
```

### 2.3 Modern Python Tooling

Add to `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py311"
line-length = 100
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]

[tool.ruff.isort]
known-first-party = ["common", "controller", "lftp", "model", "ssh", "system", "web"]

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"
pythonpath = ["."]

[tool.coverage.run]
source = ["common", "controller", "lftp", "model", "ssh", "system", "web"]
branch = true

[tool.coverage.report]
exclude_lines = ["pragma: no cover", "if TYPE_CHECKING:"]
fail_under = 80
```

### 2.4 Test Coverage Improvement

Current: ~60-70%  
Target: 80%+

**Priority areas for new tests**:

| Area | Current | Target | New Tests Needed |
|------|---------|--------|------------------|
| `common/config.py` | 75% | 90% | Edge cases |
| `controller/controller.py` | 50% | 80% | Error paths |
| `lftp/lftp.py` | 70% | 85% | Connection errors |
| `web/handlers/` | 60% | 80% | Validation |

---

## Phase 3: Angular Migration Path

**Duration**: Weeks 5-12  
**Goal**: Upgrade Angular 4.2.4 → 18.x

### Migration Strategy

Angular migrations must be done incrementally. The CLI tooling (`ng update`) handles most breaking changes automatically when upgrading one major version at a time.

```
Angular 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14 → 15 → 16 → 17 → 18
           ↑           ↑             ↑                       ↑
      RxJS 5→6     Ivy Preview    Ivy Default         Standalone
```

### 3.1 Pre-Migration Preparation (Week 5)

| Task | Effort | Notes |
|------|--------|-------|
| Generate `package-lock.json` | 30 min | Required for npm audit |
| Create comprehensive Angular tests | 4 hrs | Baseline for migration |
| Document current component behavior | 2 hrs | Screenshots, functionality notes |
| Set up migration branch | 15 min | `git checkout -b angular-migration` |

### 3.2 Angular 4 → 6 Migration (Weeks 5-6)

**Critical Changes**:
- RxJS 5 → 6 (breaking: operator syntax)
- HttpModule → HttpClientModule
- Angular CLI modernization

**Step-by-step**:

```bash
# Week 5: Angular 4 → 5
npm install @angular/{core,common,compiler,forms,http,platform-browser,platform-browser-dynamic,router,animations}@5.2.11
npm install @angular/{cli,compiler-cli,language-service}@1.7.4
npm install rxjs@5.5.12
npm install typescript@2.5.3
ng update  # Run compatibility checks

# Week 6: Angular 5 → 6 + RxJS 6
npm install @angular/{core,common,compiler,forms,http,platform-browser,platform-browser-dynamic,router,animations}@6.1.10
npm install @angular/{cli,compiler-cli,language-service}@6.2.9
npm install rxjs@6.6.7 rxjs-compat@6.6.7  # Compatibility layer first
npm install typescript@2.9.2
ng update @angular/core@6 @angular/cli@6

# Then: Remove rxjs-compat and fix imports
npm uninstall rxjs-compat
# Fix: import { map } from 'rxjs/operators';
```

**RxJS Migration Guide**:

```typescript
// Before (RxJS 5)
import { Observable } from 'rxjs/Observable';
import 'rxjs/add/operator/map';

this.http.get('/api/data')
  .map(res => res.json())
  .subscribe(data => console.log(data));

// After (RxJS 6+)
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';

this.http.get<Data>('/api/data').pipe(
  map(data => data)
).subscribe(data => console.log(data));
```

### 3.3 Angular 6 → 9 Migration (Weeks 7-8)

**Key Changes**:
- Ivy renderer (opt-in in 9)
- Differential loading
- TypeScript 3.x

```bash
# Angular 7
npm install @angular/{core,common,compiler,...}@7.2.16
npm install typescript@3.1.6

# Angular 8
npm install @angular/{core,common,compiler,...}@8.2.14
npm install typescript@3.4.5

# Angular 9 (Ivy opt-in)
npm install @angular/{core,common,compiler,...}@9.1.13
npm install typescript@3.8.3
# Enable Ivy in tsconfig.json:
# "angularCompilerOptions": { "enableIvy": true }
```

### 3.4 Angular 9 → 12 Migration (Weeks 9-10)

**Key Changes**:
- Ivy becomes default (10+)
- TSLint → ESLint migration (11+)
- Strict mode improvements

```bash
# Angular 10
ng update @angular/core@10 @angular/cli@10

# Angular 11 (ESLint migration)
ng update @angular/core@11 @angular/cli@11
ng add @angular-eslint/schematics
ng g @angular-eslint/schematics:convert-tslint-to-eslint

# Angular 12
ng update @angular/core@12 @angular/cli@12
```

### 3.5 Angular 12 → 15 Migration (Week 11)

**Key Changes**:
- Standalone components (preview in 14, stable in 15)
- esbuild for faster builds
- MDC-based Material components

```bash
ng update @angular/core@13 @angular/cli@13
ng update @angular/core@14 @angular/cli@14
ng update @angular/core@15 @angular/cli@15
```

### 3.6 Angular 15 → 18 Migration (Week 12)

**Key Changes**:
- Signals (16+)
- Control flow syntax (17+)
- Zoneless change detection (experimental)

```bash
ng update @angular/core@16 @angular/cli@16
ng update @angular/core@17 @angular/cli@17
ng update @angular/core@18 @angular/cli@18
```

### 3.7 jQuery Removal

jQuery is an anti-pattern in Angular. Remove and replace with Angular's Renderer2.

**Current jQuery usage** (audit required):
- Bootstrap JavaScript (dropdowns, modals)
- Possible DOM manipulation

**Replacement strategy**:

```typescript
// Before (jQuery)
$('#myModal').modal('show');

// After (Angular + Bootstrap 5)
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';

constructor(private modalService: NgbModal) {}

openModal() {
  this.modalService.open(MyModalComponent);
}
```

---

## Phase 4: Testing Modernization

**Duration**: Weeks 13-14  
**Goal**: Replace deprecated Protractor, improve test infrastructure

### 4.1 E2E Framework Migration

**Current**: Protractor 5.1.2 (DEPRECATED since 2021)  
**Target**: Playwright (preferred) or Cypress

**Why Playwright over Cypress**:
- Better cross-browser support
- Native async/await
- More powerful selectors
- Microsoft-backed (active development)

**Migration steps**:

```bash
# Remove Protractor
npm uninstall protractor
rm -rf e2e/

# Add Playwright
npm init playwright@latest
# Creates: playwright.config.ts, tests/, .github/workflows/playwright.yml
```

**Example test conversion**:

```typescript
// Before (Protractor)
import { browser, by, element } from 'protractor';

describe('Files Page', () => {
  it('should display file list', () => {
    browser.get('/files');
    expect(element(by.css('.file-list')).isPresent()).toBe(true);
  });
});

// After (Playwright)
import { test, expect } from '@playwright/test';

test.describe('Files Page', () => {
  test('should display file list', async ({ page }) => {
    await page.goto('/files');
    await expect(page.locator('.file-list')).toBeVisible();
  });
});
```

### 4.2 Unit Test Improvements

**Angular testing updates**:

```typescript
// Before (TestBed with deprecated patterns)
beforeEach(() => {
  TestBed.configureTestingModule({
    imports: [HttpModule],
    providers: [MyService]
  });
});

// After (Modern TestBed with HttpClientTestingModule)
beforeEach(() => {
  TestBed.configureTestingModule({
    imports: [HttpClientTestingModule],
    providers: [MyService]
  });
});
```

### 4.3 Python Test Fixtures

Create pre-bundled test archives to remove `rar` binary dependency:

```
src/python/tests/fixtures/
├── archives/
│   ├── test.rar           # Pre-created RAR archive
│   ├── test.part1.rar     # Split RAR part 1
│   ├── test.part2.rar     # Split RAR part 2
│   ├── test.zip
│   └── test.tar.gz
└── README.md              # How to regenerate fixtures
```

---

## Phase 5: Infrastructure

**Duration**: Weeks 15-16  
**Goal**: Modern DevOps practices

### 5.1 Docker Improvements

**Current issues**:
- No multi-stage builds
- Large image size
- DEB builder uses Ubuntu 16.04 (EOL)

**Target Dockerfile** (multi-stage, optimized):

```dockerfile
# Stage 1: Python dependencies
FROM python:3.12-slim AS python-deps
WORKDIR /app
RUN pip install --no-cache-dir pipx && \
    pipx install poetry && \
    pipx ensurepath
COPY src/python/pyproject.toml src/python/poetry.lock ./
RUN /root/.local/bin/poetry export -f requirements.txt --output requirements.txt && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Angular build
FROM node:22-slim AS angular-build
WORKDIR /app
COPY src/angular/package*.json ./
RUN npm ci
COPY src/angular/ ./
RUN npm run build -- --configuration=production

# Stage 3: Final image
FROM python:3.12-slim AS runtime
WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    lftp openssh-client p7zip-full \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from deps stage
COPY --from=python-deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

# Copy Angular dist from build stage
COPY --from=angular-build /app/dist /app/html

# Copy Python source
COPY src/python/ /app/python/

EXPOSE 8080
CMD ["python", "/app/python/seedsync.py"]
```

### 5.2 CI/CD Enhancements

**Current GitHub Actions workflow improvements**:

```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  python-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install poetry
          cd src/python && poetry install
      - name: Run linting
        run: cd src/python && poetry run ruff check .
      - name: Run type checking
        run: cd src/python && poetry run mypy .
      - name: Run tests with coverage
        run: cd src/python && poetry run pytest --cov --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v4

  angular-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'
          cache-dependency-path: src/angular/package-lock.json
      - name: Install dependencies
        run: cd src/angular && npm ci
      - name: Run linting
        run: cd src/angular && npm run lint
      - name: Run tests
        run: cd src/angular && npm run test -- --watch=false --browsers=ChromeHeadless

  e2e-tests:
    runs-on: ubuntu-latest
    needs: [python-tests, angular-tests]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
      - name: Install Playwright
        run: npx playwright install --with-deps
      - name: Run E2E tests
        run: npx playwright test

  docker-build:
    runs-on: ubuntu-latest
    needs: [e2e-tests]
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/build-push-action@v5
        with:
          context: .
          push: false
          tags: rapidcopy:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### 5.3 Security Scanning

Add automated security scanning:

```yaml
# .github/workflows/security.yml
name: Security Scan

on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly
  push:
    branches: [main]

jobs:
  python-security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run pip-audit
        run: |
          pip install pip-audit
          cd src/python && pip-audit -r <(poetry export -f requirements.txt)

  npm-security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run npm audit
        run: cd src/angular && npm audit --audit-level=high

  docker-security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Trivy
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
```

---

## Phase 6: Quality & Documentation

**Duration**: Weeks 17-18  
**Goal**: Production-ready documentation and quality gates

### 6.1 API Documentation

Create OpenAPI specification:

```yaml
# src/python/openapi.yaml
openapi: 3.1.0
info:
  title: RapidCopy API
  version: 1.0.0
  description: File synchronization REST API

paths:
  /api/v1/files:
    get:
      summary: List all files
      responses:
        '200':
          description: List of files
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/File'

  /api/v1/files/{name}/queue:
    post:
      summary: Queue file for download
      parameters:
        - name: name
          in: path
          required: true
          schema:
            type: string

components:
  schemas:
    File:
      type: object
      properties:
        name:
          type: string
        state:
          type: string
          enum: [DEFAULT, QUEUED, DOWNLOADING, DOWNLOADED, DELETED]
        remote_size:
          type: integer
        local_size:
          type: integer
```

### 6.2 Documentation Updates

| Document | Action | Priority |
|----------|--------|----------|
| README.md | Update for modern stack | HIGH |
| DeveloperReadme.md | Update setup instructions | HIGH |
| ARCHITECTURE.md | Create system design doc | MEDIUM |
| API.md | Generate from OpenAPI | MEDIUM |
| DEPLOYMENT.md | Production deployment guide | MEDIUM |
| TROUBLESHOOTING.md | Common issues and solutions | LOW |

### 6.3 Quality Gates

Implement pre-commit hooks:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.11.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests]

  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: poetry run pytest tests/unittests -x -q
        language: system
        pass_filenames: false
```

---

## Phase 7: Optional Enhancements

**Duration**: Weeks 19-24  
**Goal**: Feature improvements and learning opportunities

### 7.1 Backend Improvements

| Feature | Effort | Benefit |
|---------|--------|---------|
| FastAPI migration | 40 hrs | Modern async, auto docs |
| SQLite persistence | 20 hrs | Better than file-based |
| WebSocket support | 16 hrs | Replace SSE |
| API versioning | 8 hrs | `/api/v1/` prefix |
| Rate limiting | 8 hrs | Security improvement |

### 7.2 Frontend Improvements

| Feature | Effort | Benefit |
|---------|--------|---------|
| Dark mode | 8 hrs | Modern UI |
| PWA support | 16 hrs | Offline capability |
| Angular Signals | 24 hrs | Better reactivity |
| Bootstrap 5 | 8 hrs | Modern CSS |

### 7.3 Infrastructure Improvements

| Feature | Effort | Benefit |
|---------|--------|---------|
| Kubernetes Helm chart | 16 hrs | Easy deployment |
| Prometheus metrics | 8 hrs | Observability |
| Health check endpoints | 4 hrs | Container orchestration |

---

## Risk Management

### High-Risk Items

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Angular migration breaks functionality | HIGH | HIGH | Incremental upgrades, comprehensive tests |
| RxJS migration complexity | HIGH | MEDIUM | Use rxjs-compat first, then migrate |
| Test coverage gaps | MEDIUM | HIGH | Add tests before each migration step |
| Third-party library incompatibility | MEDIUM | MEDIUM | Check Angular update guide before each step |

### Rollback Strategy

1. **Git branches**: Each phase gets its own branch
2. **Docker tags**: Tag working images before major changes
3. **Database backups**: Not applicable (file-based persistence)
4. **Feature flags**: Consider for gradual rollout

---

## Success Metrics

### Phase 1-2 (Python Foundation)
- [ ] All Python tests pass on 3.11+
- [ ] Zero CVEs in Python dependencies
- [ ] 80%+ test coverage
- [ ] 90%+ type hint coverage
- [ ] Zero deprecation warnings

### Phase 3-4 (Angular Migration)
- [ ] Angular 18.x running
- [ ] All unit tests passing
- [ ] E2E tests migrated to Playwright
- [ ] Zero npm audit vulnerabilities

### Phase 5-6 (Infrastructure)
- [ ] Docker image size < 500MB
- [ ] CI/CD pipeline < 10 min
- [ ] API documentation complete
- [ ] Security scans passing

### Overall Project
- [ ] Zero known CVEs
- [ ] Build reproducible
- [ ] Tests comprehensive
- [ ] Documentation current

---

## Timeline Summary

```
Week 1-2:   Phase 1 - Foundation (Python 3.11) ████████░░░░ 80%
Week 3-4:   Phase 2 - Python Hardening          ░░░░░░░░░░░░ 0%
Week 5-12:  Phase 3 - Angular Migration         ░░░░░░░░░░░░ 0%
Week 13-14: Phase 4 - Testing Modernization     ░░░░░░░░░░░░ 0%
Week 15-16: Phase 5 - Infrastructure            ░░░░░░░░░░░░ 0%
Week 17-18: Phase 6 - Quality & Documentation   ░░░░░░░░░░░░ 0%
Week 19-24: Phase 7 - Optional Enhancements     ░░░░░░░░░░░░ 0%
```

**Total Estimated Effort**: 400-500 hours  
**Timeline**: 24 weeks @ 20 hours/week (or 12 weeks @ 40 hours/week)

---

## Appendix A: Quick Reference Commands

```bash
# Python development
cd src/python
poetry install
poetry run pytest
poetry run ruff check .
poetry run mypy .

# Angular development
cd src/angular
npm install
npm run start      # Development server
npm run test       # Unit tests
npm run build      # Production build

# Docker
make docker-image  # Build Docker image
make run-tests-python
make run-tests-angular

# Angular migration (example)
ng update @angular/core@X @angular/cli@X
```

---

## Appendix B: Key File Locations

```
src/
├── python/
│   ├── pyproject.toml      # Python dependencies
│   ├── poetry.lock         # Locked versions
│   ├── seedsync.py         # Main entry point
│   └── tests/              # Python tests
├── angular/
│   ├── package.json        # Angular dependencies
│   ├── angular.json        # CLI configuration
│   └── src/app/            # Angular source
└── docker/
    ├── build/              # Build Dockerfiles
    └── test/               # Test Dockerfiles
```

---

*Document maintained by Claude (AI-Assisted Development)*  
*Last updated: February 2026*
