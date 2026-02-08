# Updating an Existing Docker Container to the New Build

This guide describes how to update an existing SeedSync Docker container
to include the download validation feature (whole-file and chunked SHA256
validation with selective re-download).

## Overview of Changes

The new build adds:
- **Download validation**: SHA256 integrity checks after file downloads
- **Chunked validation**: Per-chunk validation with selective re-download of
  only corrupted chunks (reduces bandwidth on validation failures)
- **New config settings**: `enable_download_validation`, `download_validation_max_retries`,
  `use_chunked_validation`, `validation_chunk_size_mb`
- **New UI settings section**: "Download Validation" in the web interface

## Prerequisites

- Docker installed and running
- Access to the SeedSync Docker image (either built locally or from registry)
- Existing SeedSync container running (for migration)

## Method 1: Pull and Replace (Docker Hub)

If the new version is published to Docker Hub:

```bash
# 1. Pull the latest image
docker pull leanid/seedsync:latest

# 2. Stop the current container
docker stop seedsync

# 3. Remove the old container (data is preserved in volumes)
docker rm seedsync

# 4. Start a new container with the same volume mounts
docker run -d \
  --name seedsync \
  --restart unless-stopped \
  -p 8800:8800 \
  -v /path/to/config:/config \
  -v /path/to/downloads:/downloads \
  leanid/seedsync:latest
```

## Method 2: Build from Source

If building from the feature branch:

```bash
# 1. Clone the repository and checkout the feature branch
git clone https://github.com/rccypher/seedsync.git
cd seedsync
git checkout claude/add-download-validation-2RuYe

# 2. Build the Docker image
#    The Makefile handles multi-stage builds (Angular, Python, scanfs)
make build-docker-image

# 3. Stop and remove the existing container
docker stop seedsync
docker rm seedsync

# 4. Start a new container using the locally built image
docker run -d \
  --name seedsync \
  --restart unless-stopped \
  -p 8800:8800 \
  -v /path/to/config:/config \
  -v /path/to/downloads:/downloads \
  seedsync/run:latest
```

### Building Only the Python Backend (for development)

If you only need to test the Python backend changes:

```bash
# Build the Docker image stages
cd seedsync

# Build the Python runtime image
docker build \
  -f src/docker/build/docker-image/Dockerfile \
  --target seedsync_run_python \
  -t seedsync/run/python:dev \
  .
```

## Method 3: Docker Compose

If using Docker Compose, update your `docker-compose.yml`:

```yaml
version: "3.4"
services:
  seedsync:
    image: leanid/seedsync:latest  # or your locally built tag
    container_name: seedsync
    restart: unless-stopped
    ports:
      - "8800:8800"
    volumes:
      - /path/to/config:/config
      - /path/to/downloads:/downloads
```

Then run:

```bash
docker-compose pull    # if using registry image
docker-compose up -d   # recreates container with new image
```

## Configuration Migration

The new validation settings are automatically initialized with defaults
when the updated application starts for the first time. No manual
configuration changes are required.

### Default Values

| Setting | Default | Description |
|---------|---------|-------------|
| `enable_download_validation` | `False` | Validation is disabled by default |
| `download_validation_max_retries` | `3` | Max retry attempts on failure |
| `use_chunked_validation` | `False` | Uses whole-file mode by default |
| `validation_chunk_size_mb` | `4` | 4MB chunks when chunked mode enabled |

### Enabling Validation After Update

**Via the Web UI:**
1. Open the SeedSync web interface (default: `http://localhost:8800`)
2. Navigate to **Settings**
3. Scroll to the **Download Validation** section
4. Check **Enable Download Validation**
5. Optionally check **Enable Chunked Validation** for bandwidth-efficient repairs
6. Adjust **Max Validation Retries** and **Validation Chunk Size (MB)** as needed
7. Click **Save**

**Via the config file:**

Edit `/config/settings.cfg` (mapped from the container's `/config` volume):

```ini
[Controller]
# ... existing settings ...
enable_download_validation=True
download_validation_max_retries=3
use_chunked_validation=True
validation_chunk_size_mb=4
```

Then restart the container:
```bash
docker restart seedsync
```

## Verifying the Update

### Check Container Version

```bash
docker logs seedsync 2>&1 | head -20
```

### Verify Validation is Working

1. Enable validation in the UI
2. Queue a file for download
3. Watch the file list - after download completes, the file should briefly
   show a "Validating" state with a spinning indicator
4. Check container logs for validation messages:

```bash
docker logs -f seedsync 2>&1 | grep -i valid
```

Expected log entries:
```
Starting whole-file validation for: filename.ext
Validation PASSED for filename.ext
```

Or for chunked mode:
```
Starting chunked validation for: filename.ext
Chunked validation PASSED for filename.ext
```

### Run Tests in Docker

To run the validation tests inside a Docker test container:

```bash
cd seedsync

# Run all Python tests (includes validation tests)
make run-tests-python

# Or build and run the test container manually:
docker build \
  -f src/docker/test/python/Dockerfile \
  --target seedsync_test_python \
  -t seedsync/test/python \
  .

docker run --rm \
  -v $(pwd)/src/python:/src:ro \
  seedsync/test/python \
  pytest -v tests/unittests/test_controller/test_validate/
```

## Rollback

If the update causes issues, roll back to the previous version:

```bash
# List available image versions
docker images leanid/seedsync

# Stop and remove the new container
docker stop seedsync
docker rm seedsync

# Start with the previous version tag
docker run -d \
  --name seedsync \
  --restart unless-stopped \
  -p 8800:8800 \
  -v /path/to/config:/config \
  -v /path/to/downloads:/downloads \
  leanid/seedsync:<previous-version-tag>
```

The new config settings (`enable_download_validation`, etc.) in `settings.cfg`
will be safely ignored by older versions since unrecognized settings in the
config file do not cause errors.

## Troubleshooting

**Validation always shows ERROR:**
- Check that the remote server is accessible via SSH from inside the container
- Verify the remote path is correct in Settings > Server > Server Directory
- Check container logs: `docker logs seedsync 2>&1 | grep -i "validation error"`

**High bandwidth usage with chunked validation:**
- Increase the chunk size (e.g., 8MB or 16MB) to reduce per-chunk overhead
- Ensure `use_chunked_validation` is enabled - otherwise the whole file is
  re-downloaded on any mismatch

**Container won't start after update:**
- Check for config file syntax errors: `docker logs seedsync`
- Try starting with a fresh config: temporarily rename `/config/settings.cfg`
  and let the application regenerate defaults
