# Download Validation - Test Guide

This document describes how to run the automated test suites for the download
validation feature, including whole-file SHA256 validation, chunked validation
with selective re-download, and end-to-end integration tests.

## Test File Locations

| Test File | Type | Description |
|-----------|------|-------------|
| `tests/unittests/test_controller/test_validate/test_validate_process.py` | Unit | ValidateProcess logic, data classes, hash helpers, mocked SSH |
| `tests/unittests/test_controller/test_validate/test_config_validation.py` | Unit | Config property parsing for validation settings |
| `tests/unittests/test_controller/test_validate/test_controller_validation.py` | Unit | Controller persistence, ModelBuilder integration, serialization |
| `tests/unittests/test_ssh/test_sshcp_copy_from_remote.py` | Unit/Integration | Sshcp.copy_from_remote with real SSH server |
| `tests/integration/test_validate/test_validate_e2e.py` | E2E | Full pipeline tests with real SSH, filesystem, and chunk repair |

## Prerequisites

### Option A: Docker (Recommended)

No additional setup required. The Docker test container handles all dependencies
including the SSH server and test user account.

### Option B: Local Development

If running tests outside Docker, you must set up the SSH test environment:

```bash
# Create the test user
sudo adduser -q --disabled-password --disabled-login --gecos 'seedsynctest' seedsynctest
sudo bash -c "echo seedsynctest:seedsyncpass | chpasswd"

# Set up SSH key authentication
sudo -u seedsynctest mkdir -p /home/seedsynctest/.ssh
cat ~/.ssh/id_rsa.pub | sudo -u seedsynctest tee /home/seedsynctest/.ssh/authorized_keys
sudo -u seedsynctest chmod 664 /home/seedsynctest/.ssh/authorized_keys

# Ensure SSH server is running
sudo service ssh start
```

Install Python dependencies:
```bash
cd src/python
poetry install
```

## Running Tests

### All Tests (Docker)

```bash
# From the project root
make run-tests-python
```

This runs all Python tests (unit + integration) inside the Docker container.

### Unit Tests Only

```bash
# Docker
make run-tests-python

# Local - all unit tests
cd src/python
poetry run pytest tests/unittests -v

# Local - validation unit tests only
cd src/python
poetry run pytest tests/unittests/test_controller/test_validate/ -v
```

### Specific Test Files

```bash
# ValidateProcess tests (mocked SSH - no SSH server needed)
cd src/python
poetry run pytest tests/unittests/test_controller/test_validate/test_validate_process.py -v

# Config validation tests (no SSH server needed)
poetry run pytest tests/unittests/test_controller/test_validate/test_config_validation.py -v

# Controller/ModelBuilder validation tests (no SSH server needed)
poetry run pytest tests/unittests/test_controller/test_validate/test_controller_validation.py -v

# SSH copy_from_remote tests (requires SSH server)
poetry run pytest tests/unittests/test_ssh/test_sshcp_copy_from_remote.py -v

# End-to-end validation tests (requires SSH server)
poetry run pytest tests/integration/test_validate/test_validate_e2e.py -v
```

### Running with Detailed Logging

All test files include structured logging. To see full log output:

```bash
cd src/python
poetry run pytest tests/unittests/test_controller/test_validate/ -v -s
```

The `-s` flag disables output capture, showing all `logger.info()` and
`logger.debug()` messages in real-time.

### Running a Specific Test Case

```bash
# Run a single test method
poetry run pytest tests/unittests/test_controller/test_validate/test_validate_process.py::TestValidateProcessWholeFile::test_whole_file_pass -v -s

# Run all chunked tests
poetry run pytest tests/unittests/test_controller/test_validate/test_validate_process.py::TestValidateProcessChunkedFile -v -s

# Run all E2E chunked tests
poetry run pytest tests/integration/test_validate/test_validate_e2e.py::TestE2EChunkedValidation -v -s
```

## Test Descriptions

### Unit Tests: test_validate_process.py

**Data Model Tests:**
- `TestChunkFailure` - ChunkFailure attributes and remote_file_path
- `TestValidationResult` - PASSED/FAILED/ERROR results, chunk metadata
- `TestValidationStatus` - ValidationStatus state tracking

**Whole-File Validation (mocked SSH):**
- `TestValidateProcessWholeFile`
  - `test_whole_file_pass` - Matching hashes pass
  - `test_whole_file_fail` - Mismatched hashes fail
  - `test_whole_file_missing_local` - Missing local file returns ERROR
  - `test_whole_file_remote_ssh_error` - SSH failure returns ERROR
- `TestValidateProcessWholeDirectory`
  - `test_directory_pass` - All files match
  - `test_directory_fail_one_file` - One mismatch fails whole directory
  - `test_directory_missing_local` - Missing directory returns ERROR
  - `test_directory_empty_passes` - Empty directory passes
  - `test_directory_skips_lftp_temp_files` - .lftp files ignored
  - `test_directory_remote_error` - SSH error during directory validation

**Chunked Validation (mocked SSH):**
- `TestValidateProcessChunkedFile`
  - `test_chunked_file_pass` - All chunks match
  - `test_chunked_file_fail_repair_success` - Corrupt chunk repaired
  - `test_chunked_file_missing_local` - Missing file returns ERROR
  - `test_chunked_file_remote_hash_error` - Remote hash failure
  - `test_chunked_repair_failure` - SCP repair failure reported
- `TestValidateProcessChunkedDirectory`
  - `test_chunked_dir_pass` - All directory chunks match
  - `test_chunked_dir_missing` - Missing directory

**Helper Methods:**
- `TestCollectLocalFiles` - File collection with lftp filtering
- `TestComputeLocalSha256` - SHA256 hash computation
- `TestValidateProcessLifecycle` - Mode routing, exception handling

### Unit Tests: test_config_validation.py

- `TestControllerValidationConfig`
  - Config field parsing (bool, int, combinations)
  - Bad value rejection (non-boolean, negative, zero, strings)
  - Missing field detection
  - INI file parsing with validation fields
  - Default value verification

### Unit Tests: test_controller_validation.py

- `TestControllerPersistValidation` - Retry count tracking
- `TestModelBuilderValidation` - VALIDATING state in model builder
- `TestModelFileValidatingState` - State enum values
- `TestSerializeValidatingState` - SSE serialization of VALIDATING

### SSH Tests: test_sshcp_copy_from_remote.py

- Text and binary file copy from remote
- Error handling: bad password, missing file, bad host, empty paths
- Overwrite existing files

### E2E Tests: test_validate_e2e.py

- `TestE2EWholeFileValidation` - Real SSH whole-file validation
- `TestE2EChunkedValidation` - Real SSH chunked validation and repair
- `TestE2EValidationWorkflow` - Full controller workflow simulation

## Logging and Issue Reporting

All test files use Python's `logging` module with structured output:

```
2024-01-15 10:30:45,123 - INFO - test_validate_e2e [test_e2e_chunked_corrupt_chunk_repaired:185] - chunk repaired, 1 chunks repaired
```

Log format includes:
- **Timestamp** - When the event occurred
- **Level** - DEBUG, INFO, WARNING, ERROR
- **Logger name** - Which test module
- **Function and line** - Source location (E2E tests)
- **Message** - Human-readable description

When reporting issues, include the full test output with `-v -s` flags to
capture both pytest verbose output and application-level logging.

## Troubleshooting

**SSH connection refused:**
Ensure the SSH server is running and the seedsynctest account exists.
In Docker, the entrypoint script starts sshd automatically.

**Timeout errors:**
Integration and E2E tests have timeout decorators. If tests timeout on
slower systems, the timeout values may need adjustment. Default timeouts
are 5s for unit tests and 30-60s for E2E tests.

**Permission errors:**
The test directories need group-writable permissions for the seedsynctest
user. The `TestUtils.chmod_from_to()` helper handles this automatically.
