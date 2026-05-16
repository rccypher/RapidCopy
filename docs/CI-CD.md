# CI/CD Pipeline

RapidCopy uses GitHub Actions for continuous integration and deployment.

## Workflow Overview

The CI/CD pipeline is triggered on:
- **Push to master branch** - Runs tests and builds
- **Pull requests to master** - Runs tests and builds
- **Tags matching `vX.X.X`** - Full release workflow including publishing

## Pipeline Stages

### 1. Unit Tests (Parallel)

Two parallel jobs run unit tests:

| Job | Description | Command |
|-----|-------------|---------|
| `unittests-python` | Python backend tests | `make run-tests-python` |
| `unittests-angular` | Angular frontend tests | `make run-tests-angular` |

### 2. Build (After Tests Pass)

Two parallel build jobs:

| Job | Description | Output |
|-----|-------------|--------|
| `build-deb` | Debian package | `build/*.deb` artifact |
| `build-docker-image` | Multi-arch Docker image | Pushed to GHCR staging |

### 3. End-to-End Tests (After Builds)

| Job | Matrix | Description |
|-----|--------|-------------|
| `e2etests-deb` | ubu1604, ubu1804, ubu2004 | Tests deb installation on Ubuntu versions |
| `e2etests-docker-image` | amd64, arm64, arm/v7 | Tests Docker image on different architectures |

### 4. Publish (Tags Only)

When a version tag is pushed:

| Job | Description |
|-----|-------------|
| `publish-docker-image` | Pushes to GHCR and Docker Hub (if configured) |
| `publish-deb` | Creates GitHub Release with deb package |

## Creating a Release

1. **Update version** in `src/angular/package.json`

2. **Create and push a version tag:**
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

3. The pipeline will automatically:
   - Run all tests
   - Build deb and Docker image
   - Run e2e tests
   - Create a GitHub Release with the deb package
   - Push Docker images with version tag and `latest`

## Docker Images

### Published Registries

| Registry | Image | When |
|----------|-------|------|
| GitHub Container Registry | `ghcr.io/rccypher/rapidcopy:VERSION` | Always on release |
| Docker Hub | `DOCKERHUB_USERNAME/rapidcopy:VERSION` | If secrets configured |

### Supported Architectures

- `linux/amd64`
- `linux/arm64`
- `linux/arm/v7`

## Required Secrets

### For GHCR (automatic)

No secrets needed - uses `GITHUB_TOKEN` automatically.

### For Docker Hub (optional)

Configure these in **Settings > Secrets and variables > Actions**:

| Secret | Description |
|--------|-------------|
| `DOCKERHUB_USERNAME` | Docker Hub username |
| `DOCKERHUB_TOKEN` | Docker Hub access token (not password) |

To create a Docker Hub access token:
1. Go to https://hub.docker.com/settings/security
2. Click "New Access Token"
3. Give it a name and select "Read & Write" permissions

## Local Development

### Run Tests Locally

```bash
# Python tests
make run-tests-python

# Angular tests
make run-tests-angular
```

### Build Locally

```bash
# Build deb package
make deb

# Build Docker image (requires local registry)
make docker-image
```

### Quick Local Docker Build

For development, use the simplified Dockerfile:

```bash
docker build -f Dockerfile.local -t rapidcopy:local .
docker run -d -p 8800:8800 rapidcopy:local
```

## Troubleshooting

### Build Fails on GHCR Login

Ensure the repository has package write permissions:
1. Go to **Settings > Actions > General**
2. Under "Workflow permissions", select "Read and write permissions"

### E2E Tests Fail

E2E tests require Docker with experimental features. The workflow enables this automatically, but locally you may need to configure Docker.

### Multi-arch Build Fails

QEMU is required for cross-platform builds. The workflow sets this up automatically. Locally:

```bash
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
```

## Workflow File

The workflow is defined in `.github/workflows/master.yml`.

### Action Versions Used

| Action | Version |
|--------|---------|
| `actions/checkout` | v4 |
| `actions/upload-artifact` | v4 |
| `actions/download-artifact` | v4 |
| `docker/setup-qemu-action` | v3 |
| `docker/setup-buildx-action` | v3 |
| `docker/login-action` | v3 |
| `softprops/action-gh-release` | v2 |
