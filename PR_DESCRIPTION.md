# PR: Add download validation, multi-path mapping, disk space auto-pause, and dark mode

**Branch:** `claude/implement-download-validation-xTd9M` → `master`

---

## Summary

This PR implements four major features and comprehensive infrastructure improvements for SeedSync:

- **Download Validation** - SHA256 integrity verification of downloaded files
- **Multi-Path Mapping** - Support for multiple remote/local directory mappings
- **Auto-Pause on Low Disk Space** - Automatic download pausing when disk space runs low
- **Dark Mode** - CSS variable-based dark theme with sidebar toggle

---

## Feature Details

### 1. Download Validation (SHA256)

Validates downloaded files against their remote counterparts using SHA256 checksums, ensuring data integrity after transfer.

**How it works:**
- After a file finishes downloading (transitions from DOWNLOADING to DOWNLOADED), the controller automatically triggers validation
- A new `VALIDATING` state is shown in the UI while validation is in progress
- Supports two modes: **whole-file validation** (default) and **chunked validation**
- Chunked validation splits files into configurable chunks (default 50MB), validates each independently, and can selectively re-download only corrupted chunks
- Validation runs via SSH, executing a self-contained Python script (`scanfs_standalone.py`) on the remote server to compute checksums
- Failed validations are retried up to a configurable number of times before marking as failed

**New config options** (Settings > General):

| Option | Default | Description |
|--------|---------|-------------|
| `enable_download_validation` | `True` | Enable/disable post-download SHA256 validation |
| `use_chunked_validation` | `False` | Use chunked validation instead of whole-file |
| `validation_chunk_size_mb` | `50` | Chunk size in MB for chunked validation |
| `download_validation_max_retries` | `3` | Max retry attempts for failed validations |

**Key files:**
- `src/python/controller/validate/validate_process.py` - Core validation engine (SHA256 whole-file + chunked)
- `src/python/scanfs_standalone.py` - Self-contained script deployed to remote server for checksum computation
- `src/python/controller/controller.py` - Integration with download lifecycle
- `src/python/model/file.py` - New `VALIDATING` state
- `src/angular/src/assets/icons/validating.svg` - UI icon for validating state

---

### 2. Multi-Path Mapping

Allows configuring multiple remote-to-local directory mappings, so different remote directories can sync to different local directories.

**How it works:**
- A new `[PathMappings]` config section stores JSON-encoded path mapping pairs
- Each mapping has a `remote_path` and `local_path`
- Files are assigned a `mapping_index` indicating which mapping they belong to
- The controller, LFTP, and scanners operate per-mapping, scanning and downloading files according to their assigned mapping
- The first mapping (index 0) uses the legacy `[Lftp] remote_path` and `[Controller] local_path` for backward compatibility

**New config section:**
```ini
[PathMappings]
mappings = [{"remote_path": "/remote/path1", "local_path": "/local/path1"}, {"remote_path": "/remote/path2", "local_path": "/local/path2"}]
```

**Angular Settings UI:**
- New "Path Mappings" section in Settings page
- Add/remove mapping pairs with remote/local path fields
- Visual editor with add/delete buttons

**Key files:**
- `src/python/common/config.py` - `PathMappings` config section with JSON parsing
- `src/python/model/file.py` - `mapping_index` property on `ModelFile`
- `src/python/controller/model_builder.py` - Per-mapping file merging
- `src/python/controller/controller.py` - Per-mapping download orchestration
- `src/python/lftp/lftp.py` - Dynamic base path setting per mapping
- `src/angular/src/app/pages/settings/settings-page.component.*` - Path mappings editor UI

---

### 3. Auto-Pause on Low Disk Space

Automatically pauses all downloads when the destination disk drops below a configurable threshold, preventing disk-full errors.

**How it works:**
- The controller periodically checks available disk space on the local download directory
- When free space drops below the configured threshold percentage, all active LFTP downloads are killed
- A `downloads_paused_disk_space` flag is set in the Status object and streamed to the frontend via SSE
- The frontend displays a warning notification in the header when downloads are paused
- Downloads automatically resume when disk space is freed above the threshold

**New config options** (Settings > General):

| Option | Default | Description |
|--------|---------|-------------|
| `enable_disk_space_check` | `True` | Enable automatic disk space monitoring |
| `disk_space_threshold_percent` | `10` | Pause downloads when free space drops below this % |

**Key files:**
- `src/python/controller/controller.py` - Disk space checking logic in main control loop
- `src/python/common/config.py` - Disk space config options
- `src/python/common/status.py` - `downloads_paused_disk_space` status field
- `src/python/web/serialize/serialize_status.py` - SSE serialization of disk space status
- `src/angular/src/app/pages/main/header.component.ts` - Warning display in header

---

### 4. Dark Mode

A CSS variable-based dark theme with a toggle in the sidebar.

**How it works:**
- All colors defined as CSS custom properties in `styles.scss`
- Theme toggled via moon/sun icon button in the sidebar
- Theme preference persisted in `localStorage`
- Respects `prefers-color-scheme` media query for initial theme
- All existing components updated to use CSS variables instead of hardcoded colors

**Key files:**
- `src/angular/src/styles.scss` - CSS variable definitions for light/dark themes
- `src/angular/src/app/pages/main/sidebar.component.*` - Theme toggle button
- All component `.scss` files - Updated to use `var(--color-name)` references
- `src/angular/src/assets/icons/moon.svg`, `sun.svg` - Theme toggle icons

---

## Infrastructure & Build Changes

- **Dockerfile** (root) - New simplified all-in-one Dockerfile for easy local builds
- **Docker build fixes** - Updated base images and pip installer URLs for newer Debian
- **Angular build fixes** - `skipLibCheck` in tsconfig, fixed output directory in Dockerfile
- **Poetry pinning** - Pinned Poetry to 1.5.1 for Python 3.8 compatibility
- **SSH quoting fix** - Handle commands with both single and double quotes
- **Pickle compatibility** - Fixed module path issues between `scanfs_standalone.py` and main app
- **Regex escape sequences** - Fixed invalid escape sequences for Python 3.12+ compatibility

---

## Documentation

- `doc/DockerUpdateGuide.md` - Comprehensive Docker setup and update guide
- `doc/ValidationTestGuide.md` - Guide for testing the download validation feature
- `src/python/docs/usage.md` - Updated usage documentation with all new features
- `src/python/docs/faq.md` - FAQ for common questions about new features

---

## Test Coverage

**75 files changed, ~6,200 lines added**

| Feature | Unit Tests | Integration Tests | Config Tests |
|---------|-----------|-------------------|--------------|
| Download Validation | 51 (validate_process) + 25 (controller_validation) | 18 (e2e) | 12 (config_validation) |
| Multi-Path Mapping | 14 (model_builder_multipath) | - | 4 (config) |
| Auto-Pause Disk Space | 16 (disk_space) | - | 4 (config) |
| Serialization | 7 (status_disk_space) + 8 (model_new_features) | - | - |

**Total: ~159 new tests**

---

## Commits (33 total)

1. `993e894` - Add download validation feature with configurable UI settings
2. `c85f8f7` - Switch validation algorithm from MD5 to SHA256
3. `34cc46b` - Add chunked validation with selective chunk re-download
4. `93ce3dd` - Add comprehensive tests and documentation for download validation
5. `f7e5629` - Add simplified all-in-one Dockerfile for easy local builds
6. `20266a6` - Fix Dockerfile for newer Debian base images
7. `786fc42` - Fix pip installer URL for Python 3.8
8. `b839e54` - Fix Angular build output directory in Dockerfile
9. `b50c7dd` - Add skipLibCheck to Angular tsconfig
10. `72d8024` - Add self-contained scanfs script for remote server execution
11. `fb00528` - Fix regex escape sequences in scanfs_standalone for Python 3.12+
12. `ea5d9fc` - Fix pickle module path for SystemFile in scanfs_standalone
13. `f1f9862` - Fix pickle compatibility between standalone scanfs and seedsync
14. `8e2535d` - Disable chunked validation options when download validation is off
15. `3bd0687` - Fix SSH shell quoting to handle commands with both quote types
16. `d6d4b26` - Keep files in VALIDATING state until validation passes
17. `ca3de8f` - Integrate validation into download process and enable by default
18. `c6e6851` - Fix VALIDATING state in model builder and serializer
19. `69644de` - Fix Dockerfiles for newer Debian base images
20. `8cab3ee` - Pin Poetry to 1.5.1 for Python 3.8 compatibility
21. `8825d24` - Add set_base_logger method to ValidateProcess
22. `301814f` - Add VALIDATING state support to Angular frontend
23. `ea1d278` - Add PathMappings config section for multi-path support
24. `c35ed16` - Add mapping_index to ModelFile for multi-path support
25. `0ef110b` - Update ModelBuilder for multi-path mapping support
26. `b49777b` - Update Controller and LFTP for multi-path mapping support
27. `6e7c47b` - Add path mappings editor to Angular settings UI
28. `263f519` - Fix TypeScript build error: access pathmappings as property
29. `cd181ab` - Update documentation for multi-path mapping and download validation
30. `090faed` - Add auto-pause downloads on low disk space
31. `2961387` - Add dark mode with theme toggle in sidebar
32. `3d26dbe` - Add comprehensive test suite for multi-path mapping, disk space, and serialization

---

## Codebase Modernization Recommendations (follow-up work)

The following modernization steps are recommended for long-term supportability (not included in this PR):

### Critical (Blocking Python 3.11+ upgrade)
- [ ] Replace `distutils.strtobool` (removed in Python 3.12) with inline implementation
- [ ] Replace `timeout-decorator` package (doesn't build on Python 3.11+) with `pytest.mark.timeout`
- [ ] Update `pyproject.toml` to target Python 3.11+
- [ ] Update Dockerfile base images from Python 3.8 to 3.11+

### High Priority
- [ ] Migrate 290+ `.format()` calls to f-strings
- [ ] Replace `type(x) == Y` checks with `isinstance()` (15+ instances in model/file.py)
- [ ] Pin dependency versions in `pyproject.toml` (currently all use `"*"`)
- [ ] Update pytest from 6.2.1 to 7.4+
- [ ] Add return type hints to 30+ public methods

### Medium Priority
- [ ] Angular upgrade (currently v4.2.4, 15 major versions behind)
- [ ] Update GitHub Actions from v1/v2 to v3/v4
- [ ] Add `mypy` strict type checking
- [ ] Use raw strings for regex patterns (10+ files)

---

## Test plan

- [x] All 275 Python unit tests pass (`make run-tests-python`)
- [x] Download validation e2e tests pass (18 tests)
- [x] Multi-path mapping model builder tests pass (14 tests)
- [x] Disk space tests pass (16 tests)
- [x] Serialization tests pass (15 tests)
- [ ] Manual: Docker build and run with `docker build -f Dockerfile -t seedsync:local .`
- [ ] Manual: Configure path mappings in Settings UI
- [ ] Manual: Verify dark mode toggle in sidebar
- [ ] Manual: Test download validation with a real remote server
- [ ] Manual: Test disk space auto-pause by filling disk near threshold
