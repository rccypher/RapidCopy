# Usage

## Dashboard

The Dashboard page shows all the files and directories on the remote server and the local machine.
Here you can manually queue files to be transferred, extract archives and delete files.

Files may show the following states:

| State | Description |
|-------|-------------|
| Default | File exists on the remote server but has not been queued |
| Queued | File is waiting to be downloaded |
| Downloading | File is currently being transferred |
| Downloaded | File has been fully downloaded |
| Extracting | Archive is being extracted |
| Extracted | Archive has been extracted |
| Validating | File integrity is being verified (see [Download Validation](#download-validation)) |
| Deleted | File has been deleted |

## AutoQueue

AutoQueue queues all newly discovered files on the remote server.
You can also restrict AutoQueue to pattern-based matches (see this option in the Settings page).
When pattern restriction is enabled, the AutoQueue page is where you can add or remove patterns.
Any files or directories on the remote server that match a pattern will be automatically queued for transfer.

## Path Mappings

Path Mappings allow you to sync files from multiple remote directories to different local directories.
Each mapping defines a remote path on the server and a corresponding local path where downloaded files
are placed.

### Configuring Path Mappings

1. Open the Settings page from the menu.
2. Expand the **Path Mappings** section.
3. Each mapping has two fields:
    - **Remote Path**: The directory on the remote server to scan for files (e.g. `/home/user/files`).
    - **Local Path**: The directory on the local machine where files will be downloaded (e.g. `/downloads/files`).
4. Click **+ Add Path Mapping** to add additional mappings.
5. Click **Remove** to delete a mapping (at least one mapping must exist).
6. Click **Restart** to apply the changes.

### How It Works

- SeedSync creates independent scanners for each path mapping.
- Files from all mappings appear together on the Dashboard.
- When a file is queued, SeedSync automatically uses the correct remote and local paths based on
  which mapping the file belongs to.
- If the same filename exists in multiple mappings, a warning is logged and the first mapping takes priority.

### Example

| Remote Path | Local Path |
|-------------|------------|
| `/home/user/movies` | `/downloads/movies` |
| `/home/user/music` | `/downloads/music` |
| `/home/user/software` | `/downloads/software` |

This configuration will scan three directories on the remote server and download files to the
corresponding local directories.

!!! note
    When using Docker, the local paths must be paths inside the container. Mount host directories
    to container paths using Docker's `-v` option. For example:
    ```
    -v /media/movies:/downloads/movies
    -v /media/music:/downloads/music
    ```

## Download Validation

Download Validation verifies the integrity of downloaded files by comparing SHA256 checksums between
the remote and local copies. This ensures files were transferred without corruption.

### Configuring Download Validation

1. Open the Settings page from the menu.
2. Expand the **Download Validation** section.
3. Configure the following settings:

| Setting | Description |
|---------|-------------|
| Max Validation Retries | Number of times to re-download a file that fails validation (default: 3) |
| Chunk Size (MB) | Size of each chunk for chunked validation (default: 4 MB) |

Validation is enabled automatically when the settings are configured. After a file finishes downloading,
it will briefly enter the **Validating** state while integrity checks are performed.

### Validation Modes

**Whole-File Validation**

- Computes a single SHA256 hash of the entire file on both the remote server and local machine.
- If the hashes don't match, the entire file is re-downloaded.
- Best for smaller files or when bandwidth is not a concern.

**Chunked Validation**

- Splits the file into chunks (configurable size) and validates each chunk independently.
- If a chunk fails validation, only that chunk is re-downloaded instead of the entire file.
- Significantly reduces bandwidth usage when only a small portion of a large file is corrupted.
- Enable by setting `use_chunked_validation` to `True` in the config file.

### Config File Settings

The following settings can also be configured directly in `settings.cfg`:

```ini
[Controller]
enable_download_validation = True
download_validation_max_retries = 3
use_chunked_validation = True
validation_chunk_size_mb = 4
```