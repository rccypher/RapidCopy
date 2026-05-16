<p align="center">
    <img src="https://raw.githubusercontent.com/rccypher/RapidCopy/master/doc/images/rapidcopy-logo.png" alt="RapidCopy" />
</p>

<p align="center">
    <a href="#features">Features</a> &nbsp;&bull;&nbsp;
    <a href="#installation">Download</a> &nbsp;&bull;&nbsp;
    <a href="../../issues">Support</a>
</p>

<p align="center">
  <a href="https://github.com/rccypher/RapidCopy">
    <img src="https://img.shields.io/github/stars/rccypher/RapidCopy" alt="Stars">
  </a>
  <a href="https://github.com/rccypher/RapidCopy/blob/master/LICENSE.txt">
    <img src="https://img.shields.io/github/license/rccypher/RapidCopy" alt="License">
  </a>
</p>

**RapidCopy** is a high-performance file sync tool that downloads files from a remote Linux server to your local machine. Built on top of [LFTP](http://lftp.tech/) for blazing-fast multi-segment transfers, it provides a modern web UI to track and control everything from anywhere.

---

## Features

- **LFTP-Powered Transfers** - Built on [LFTP](http://lftp.tech/), the fastest file transfer program, with parallel segment downloads
- **Web Dashboard** - Track and control all your transfers from any browser
- **Multi-Path Mapping** - Sync multiple remote directories to different local directories simultaneously
- **Download Validation** - SHA256 integrity checks ensure files arrive without corruption; optional chunked validation re-downloads only corrupted portions
- **Auto-Pause on Low Disk Space** - Automatically pauses downloads when disk space runs low, resumes when space is freed
- **Dark Mode** - Toggle between light and dark themes from the sidebar
- **Auto-Extract** - Automatically extract archives after sync completes
- **Auto-Queue** - Automatically sync new files based on pattern matching rules
- **File Management** - Delete local and remote files directly from the web UI
- **Fully Open Source** - Apache 2.0 licensed

## How It Works

Install RapidCopy on your local machine (or run via Docker). RapidCopy connects to your remote server over SSH and syncs files to local storage as they become available.

**No software needs to be installed on the remote server.** All you need are SSH credentials.

## Supported Platforms

| Platform | Docker | Deb Package |
|----------|:------:|:-----------:|
| Linux/Ubuntu 64-bit | &#9989; | &#9989; |
| Raspberry Pi (v2, v3, v4) | &#9989; | |
| Windows | &#9989; | |
| macOS | &#9989; | |

---

## Installation

### Docker (Recommended)

The fastest way to get started:

```bash
docker run -d \
  --name rapidcopy \
  --restart unless-stopped \
  -p 8800:8800 \
  -v ~/rapidcopy-config:/config \
  -v ~/rapidcopy-downloads:/downloads \
  rccypher/rapidcopy:latest
```

Then open [http://localhost:8800](http://localhost:8800) in your browser.

### Build from Source (Docker)

```bash
git clone https://github.com/rccypher/RapidCopy.git
cd RapidCopy
docker build -f Dockerfile -t rapidcopy:local .

docker run -d \
  --name rapidcopy \
  --restart unless-stopped \
  -p 8800:8800 \
  -v ~/rapidcopy-config:/config \
  -v ~/rapidcopy-downloads:/downloads \
  rapidcopy:local
```

### Docker Compose

```yaml
services:
  rapidcopy:
    image: rccypher/rapidcopy:latest
    container_name: rapidcopy
    restart: unless-stopped
    ports:
      - "8800:8800"
    volumes:
      - ./config:/config
      - ./downloads:/downloads
```

### Deb Package (Ubuntu/Debian)

Download the `.deb` from the [latest release](https://github.com/rccypher/RapidCopy/releases/latest), then:

```bash
sudo dpkg -i rapidcopy_*.deb
```

---

## Quick Start

1. Open the web UI at [http://localhost:8800](http://localhost:8800)
2. Go to **Settings** and configure:
   - **Server**: Remote server address, SSH port, username, and password
   - **Path Mappings**: At least one remote/local directory pair
3. Files will appear on the Dashboard as the remote server is scanned
4. Click a file to queue it for download, or enable **Auto-Queue** for automatic syncing

### SSH Key Authentication (Recommended)

Password-based SSH is supported but key-based authentication is strongly recommended:

1. Generate an SSH key pair if you don't have one: `ssh-keygen`
2. Copy your public key to the remote server: `ssh-copy-id user@remote-server`
3. When using Docker, mount your SSH keys:
   ```bash
   -v ~/.ssh:/home/seedsync/.ssh
   ```
4. In Settings, replace the password with any placeholder and check "Use password-less key-based authentication"

---

## Configuration

### Path Mappings

Sync files from multiple remote directories to different local directories:

| Remote Path | Local Path |
|-------------|------------|
| `/home/user/movies` | `/downloads/movies` |
| `/home/user/music` | `/downloads/music` |
| `/home/user/software` | `/downloads/software` |

Configure via the Settings page or directly in `settings.cfg`:

```ini
[PathMappings]
mappings_json = [{"remote_path": "/home/user/movies", "local_path": "/downloads/movies"}, {"remote_path": "/home/user/music", "local_path": "/downloads/music"}]
```

When using Docker with multiple local paths, mount each directory:

```bash
docker run -d \
  --name rapidcopy \
  -p 8800:8800 \
  -v ~/rapidcopy-config:/config \
  -v /media/movies:/downloads/movies \
  -v /media/music:/downloads/music \
  rccypher/rapidcopy:latest
```

### Download Validation

SHA256 integrity verification runs automatically after each download. Configure in Settings or `settings.cfg`:

| Setting | Default | Description |
|---------|---------|-------------|
| `enable_download_validation` | `True` | Enable/disable post-download validation |
| `use_chunked_validation` | `False` | Validate per-chunk instead of whole file |
| `validation_chunk_size_mb` | `50` | Chunk size for chunked validation |
| `download_validation_max_retries` | `3` | Max re-download attempts on failure |

**Chunked validation** is ideal for large files - if only a small portion is corrupted, only that chunk is re-downloaded instead of the entire file.

### Disk Space Protection

Downloads automatically pause when free disk space drops below a configurable threshold:

| Setting | Default | Description |
|---------|---------|-------------|
| `enable_disk_space_check` | `True` | Enable disk space monitoring |
| `disk_space_threshold_percent` | `10` | Pause when free space drops below this % |

A warning banner appears in the web UI when downloads are paused due to low disk space. Downloads resume automatically when space is freed.

### Dark Mode

Toggle dark mode using the moon/sun icon in the sidebar. Your preference is saved in the browser.

---

## File States

Files on the Dashboard show the following states:

| State | Description |
|-------|-------------|
| Default | File exists on remote server, not yet queued |
| Queued | Waiting to be downloaded |
| Downloading | Transfer in progress |
| Validating | SHA256 integrity check in progress |
| Downloaded | Transfer complete and validated |
| Extracting | Archive extraction in progress |
| Extracted | Archive has been extracted |
| Deleted | File has been deleted |

---

## Report an Issue

Please report issues on the [Issues](../../issues) page. Include logs for faster resolution:

- **Docker**: `docker logs rapidcopy`
- **Deb install**: `~/.seedsync/log/seedsync.log`

---

## Contribute

Contributions are welcome! See the [Developer Readme](doc/DeveloperReadme.md) for environment setup and build instructions.

---

## License

RapidCopy is distributed under the Apache License Version 2.0.
See [LICENSE.txt](LICENSE.txt) for details.
