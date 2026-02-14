# RapidCopy - Use Cases and Features

This document provides a comprehensive breakdown of all use cases and features in RapidCopy, organized by user goals and system capabilities.

---

## Table of Contents

1. [Product Overview](#1-product-overview)
2. [User Personas](#2-user-personas)
3. [Use Cases](#3-use-cases)
4. [Feature Inventory](#4-feature-inventory)
5. [System Architecture](#5-system-architecture)
6. [API Surface](#6-api-surface)
7. [Data Models](#7-data-models)
8. [Configuration Options](#8-configuration-options)
9. [Non-Functional Requirements](#9-non-functional-requirements)

---

## 1. Product Overview

### 1.1 What is RapidCopy?

RapidCopy is a **file synchronization tool** that automatically downloads files from remote Linux servers to local storage. It uses LFTP for high-performance SFTP transfers with parallel connections.

### 1.2 Primary Value Proposition

| Problem | Solution |
|---------|----------|
| Manually downloading files from seedboxes/servers is tedious | Automatic discovery and download of new files |
| Single-threaded transfers are slow | Multi-segment parallel downloads via LFTP |
| No visibility into download progress | Real-time web UI with progress tracking |
| Downloaded archives need manual extraction | Automatic archive extraction post-download |
| Hard to download to NAS/network storage | Network mount support (NFS/SMB) |

### 1.3 Core Workflow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Remote    │     │  RapidCopy  │     │   Local     │     │    User     │
│   Server    │     │   Engine    │     │  Storage    │     │   Web UI    │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │                   │
       │◄──── Scan ────────│                   │                   │
       │                   │                   │                   │
       │──── File List ───►│                   │                   │
       │                   │                   │                   │
       │                   │────── Update ─────────────────────────►
       │                   │                   │                   │
       │                   │◄──────────────────────── Queue ───────│
       │                   │                   │                   │
       │◄─── Download ─────│                   │                   │
       │                   │                   │                   │
       │──── File Data ───►│───── Write ──────►│                   │
       │                   │                   │                   │
       │                   │───── Progress ────────────────────────►
       │                   │                   │                   │
       │                   │──── Extract ─────►│                   │
       │                   │                   │                   │
       │                   │────── Done ───────────────────────────►
       │                   │                   │                   │
```

---

## 2. User Personas

### 2.1 Primary Persona: Media Enthusiast

**Name:** Alex
**Role:** Home media server owner
**Goals:**
- Automatically sync media files from seedbox to Plex server
- Queue specific files for priority download
- Download directly to NAS storage
- Minimal manual intervention

### 2.2 Secondary Persona: System Administrator

**Name:** Jordan
**Role:** DevOps/SysAdmin
**Goals:**
- Sync backup files from remote servers
- Monitor transfer status and logs
- Configure multiple source/destination pairs
- Integrate with existing infrastructure (Docker, NFS)

### 2.3 Tertiary Persona: Power User

**Name:** Sam
**Role:** Technical hobbyist
**Goals:**
- Fine-tune download performance settings
- Use regex patterns for auto-queue
- Validate file integrity after transfer
- Self-host and customize

---

## 3. Use Cases

### 3.1 File Discovery & Monitoring

#### UC-1.1: View Available Files
**Actor:** User
**Goal:** See all files available on the remote server
**Preconditions:** Remote server configured and accessible
**Flow:**
1. User opens Dashboard
2. System displays list of all remote files
3. Each file shows: name, size, status, path pair
4. List updates in real-time as new files appear

**Acceptance Criteria:**
- [ ] Files appear within configured scan interval
- [ ] Unicode filenames display correctly
- [ ] Large file lists are performant (virtual scrolling)

#### UC-1.2: Filter Files by Name
**Actor:** User
**Goal:** Find specific files in a large list
**Flow:**
1. User enters search text in filter box
2. System filters list to matching files
3. User can pin filter to persist across sessions

#### UC-1.3: Filter Files by Status
**Actor:** User
**Goal:** View only files in a specific state
**Flow:**
1. User selects status from dropdown (Queued, Downloading, etc.)
2. System shows only files matching that status

#### UC-1.4: Sort File List
**Actor:** User
**Goal:** Organize files by preference
**Flow:**
1. User selects sort method (Name, Status, Size)
2. User optionally toggles ascending/descending
3. Sort preference persists across sessions

---

### 3.2 File Download

#### UC-2.1: Queue Single File for Download
**Actor:** User
**Goal:** Start downloading a specific file
**Flow:**
1. User locates file in Dashboard
2. User clicks "Queue" button
3. System adds file to download queue
4. File status changes to "Queued"
5. When slot available, status changes to "Downloading"

#### UC-2.2: Queue Multiple Files
**Actor:** User
**Goal:** Download several files at once
**Flow:**
1. User selects multiple files using checkboxes
2. User clicks "Queue All Selected"
3. System queues all selected files

#### UC-2.3: Stop Active Download
**Actor:** User
**Goal:** Cancel an in-progress download
**Flow:**
1. User locates downloading file
2. User clicks "Stop" button
3. System terminates LFTP process
4. File status changes to "Stopped"
5. Partial file retained for resume

#### UC-2.4: Retry Failed Download
**Actor:** User
**Goal:** Resume a stopped or failed download
**Flow:**
1. User locates stopped file
2. User clicks "Retry" button
3. System re-queues file
4. Download resumes from existing progress

#### UC-2.5: Monitor Download Progress
**Actor:** User
**Goal:** Track download status in real-time
**Flow:**
1. User views Dashboard
2. System displays for each downloading file:
   - Progress percentage
   - Current speed (MB/s)
   - Estimated time remaining
   - Downloaded size / total size
3. Updates occur every 2 seconds (configurable)

---

### 3.3 Auto-Queue

#### UC-3.1: Create Auto-Queue Pattern
**Actor:** User
**Goal:** Automatically download files matching a pattern
**Flow:**
1. User navigates to AutoQueue page
2. User clicks "Add Pattern"
3. User enters regex pattern (e.g., `.*\.mkv$`)
4. System saves pattern
5. Future matching files are auto-queued

#### UC-3.2: Test Pattern Before Saving
**Actor:** User
**Goal:** Verify pattern matches expected files
**Flow:**
1. User enters pattern in form
2. User clicks "Test"
3. System shows which current files would match

#### UC-3.3: Disable Pattern Temporarily
**Actor:** User
**Goal:** Pause auto-queue without deleting pattern
**Flow:**
1. User toggles pattern's enabled switch
2. System stops matching against this pattern
3. Pattern retained for later re-enable

---

### 3.4 Path Pairs

#### UC-4.1: Configure Multiple Source/Destination Pairs
**Actor:** User
**Goal:** Sync different remote folders to different local folders
**Flow:**
1. User navigates to Settings > Path Pairs
2. User clicks "Add Path Pair"
3. User enters:
   - Name (e.g., "Movies")
   - Remote path (e.g., `/home/user/movies`)
   - Local path (e.g., `/downloads/movies`)
4. System validates paths
5. System begins scanning new path pair

#### UC-4.2: View Path Pair Statistics
**Actor:** User
**Goal:** See download stats per path pair
**Flow:**
1. User views Dashboard
2. Path pair statistics panel shows:
   - Files per path pair
   - Total size per path pair
   - Active downloads per path pair

#### UC-4.3: Enable/Disable Path Pair
**Actor:** User
**Goal:** Temporarily stop syncing a path pair
**Flow:**
1. User locates path pair in Settings
2. User toggles enabled switch
3. System stops scanning that remote path

---

### 3.5 Network Mounts

#### UC-5.1: Mount NFS Share
**Actor:** User
**Goal:** Download files directly to NAS via NFS
**Flow:**
1. User navigates to Settings > Network Mounts
2. User clicks "Add Network Mount"
3. User selects Type: NFS
4. User enters:
   - Name (e.g., "NAS Media")
   - Server (e.g., `nas.local`)
   - Export path (e.g., `/volume1/media`)
   - Mount options (e.g., `vers=4,rw`)
5. System creates mount configuration
6. User clicks "Mount"
7. System mounts share to `/mounts/<name>`
8. User can now use mount path in Path Pairs

#### UC-5.2: Mount SMB/CIFS Share
**Actor:** User
**Goal:** Download files to Windows share
**Flow:**
1. User creates mount with Type: SMB/CIFS
2. User enters share name and credentials
3. System mounts share with authentication

#### UC-5.3: Auto-Mount on Startup
**Actor:** System
**Goal:** Restore mounts after restart
**Flow:**
1. System starts
2. System reads enabled mount configurations
3. System attempts to mount each enabled share
4. Failed mounts logged as warnings (non-blocking)

---

### 3.6 Archive Extraction

#### UC-6.1: Automatic Archive Extraction
**Actor:** System
**Goal:** Extract archives after download completes
**Flow:**
1. Download completes for archive file (.rar, .zip, .7z)
2. System detects extractable archive
3. File status changes to "Extracting"
4. System extracts using 7z/unrar
5. Status changes to "Extracted"
6. Extracted files appear in local path

#### UC-6.2: Manual Archive Extraction
**Actor:** User
**Goal:** Extract archive on demand
**Flow:**
1. User locates downloaded archive
2. User clicks "Extract" button
3. System begins extraction process

#### UC-6.3: Configure Extraction Path
**Actor:** User
**Goal:** Extract archives to different location
**Flow:**
1. User navigates to Settings > Post-Processing
2. User configures:
   - Extract to download directory (default)
   - Or specify custom extraction path

---

### 3.7 File Validation

#### UC-7.1: Validate Downloaded File
**Actor:** User
**Goal:** Verify file integrity via checksum
**Flow:**
1. User locates downloaded file
2. User clicks "Validate" button
3. System computes local hash
4. System fetches remote hash (if available)
5. System compares hashes
6. Status changes to "Validated" or "Corrupt"

#### UC-7.2: Automatic Validation
**Actor:** System
**Goal:** Validate files automatically after download
**Flow:**
1. Validation enabled in settings
2. Download completes
3. System automatically validates
4. Result stored with file

---

### 3.8 File Deletion

#### UC-8.1: Delete Local File
**Actor:** User
**Goal:** Remove downloaded file from local storage
**Flow:**
1. User locates file
2. User clicks "Delete Local"
3. System shows confirmation dialog
4. System deletes local file
5. Remote file unchanged

#### UC-8.2: Delete Remote File
**Actor:** User
**Goal:** Remove source file from remote server
**Flow:**
1. User locates file
2. User clicks "Delete Remote"
3. System shows confirmation dialog
4. System deletes remote file via SFTP
5. File removed from list on next scan

---

### 3.9 Logging & Monitoring

#### UC-9.1: View Real-Time Logs
**Actor:** User
**Goal:** Monitor system activity
**Flow:**
1. User navigates to Logs page
2. System streams log entries in real-time
3. User sees: timestamp, level, message, component

#### UC-9.2: Filter Logs by Level
**Actor:** User
**Goal:** Focus on specific log severity
**Flow:**
1. User selects level (DEBUG, INFO, WARNING, ERROR)
2. System shows only logs at or above that level

#### UC-9.3: Search Logs
**Actor:** User
**Goal:** Find specific log entries
**Flow:**
1. User enters search text
2. System highlights matching entries

---

### 3.10 Server Management

#### UC-10.1: Restart Server
**Actor:** User
**Goal:** Restart RapidCopy service
**Flow:**
1. User clicks Restart in sidebar
2. System shows confirmation
3. System gracefully shuts down
4. System restarts
5. User reconnects to UI

#### UC-10.2: Check for Updates
**Actor:** User
**Goal:** See if newer version available
**Flow:**
1. User navigates to About page
2. System checks update server
3. System displays current vs. available version
4. User can trigger update if available

---

### 3.11 UI Customization

#### UC-11.1: Toggle Dark Mode
**Actor:** User
**Goal:** Switch between light and dark themes
**Flow:**
1. User clicks Dark Mode toggle in sidebar
2. System switches theme immediately
3. Preference saved to localStorage
4. Theme persists across sessions

#### UC-11.2: Show/Hide File Details
**Actor:** User
**Goal:** Control information density
**Flow:**
1. User clicks Details toggle
2. System shows/hides expanded file information
3. Preference persists across sessions

---

## 4. Feature Inventory

### 4.1 Core Features

| ID | Feature | Description | Status |
|----|---------|-------------|--------|
| F-001 | Remote File Discovery | Scan remote server for available files | Implemented |
| F-002 | Multi-Segment Download | Parallel connections per file via LFTP | Implemented |
| F-003 | Download Queue | Queue management with parallel download slots | Implemented |
| F-004 | Real-Time Progress | Live progress, speed, ETA updates | Implemented |
| F-005 | Download Resume | Resume interrupted downloads | Implemented |
| F-006 | File State Tracking | Track files through complete lifecycle | Implemented |

### 4.2 Path Management Features

| ID | Feature | Description | Status |
|----|---------|-------------|--------|
| F-010 | Multiple Path Pairs | Configure multiple remote/local mappings | Implemented |
| F-011 | Path Pair Statistics | Per-pair download statistics | Implemented |
| F-012 | Path Pair Enable/Disable | Toggle individual path pairs | Implemented |
| F-013 | Path Validation | Validate path accessibility | Implemented |

### 4.3 Network Mount Features

| ID | Feature | Description | Status |
|----|---------|-------------|--------|
| F-020 | NFS Mount Support | Mount NFS shares for download destination | Implemented |
| F-021 | SMB/CIFS Mount Support | Mount Windows shares with authentication | Implemented |
| F-022 | Auto-Mount on Startup | Restore enabled mounts on service start | Implemented |
| F-023 | Mount Status Monitoring | Track mount health and status | Implemented |
| F-024 | Mount Credential Storage | Securely store SMB credentials | Implemented |

### 4.4 Auto-Queue Features

| ID | Feature | Description | Status |
|----|---------|-------------|--------|
| F-030 | Pattern-Based Auto-Queue | Auto-queue files matching regex patterns | Implemented |
| F-031 | Pattern Management | CRUD operations for patterns | Implemented |
| F-032 | Pattern Enable/Disable | Toggle individual patterns | Implemented |
| F-033 | Pattern Testing | Test pattern against current files | Implemented |

### 4.5 Post-Processing Features

| ID | Feature | Description | Status |
|----|---------|-------------|--------|
| F-040 | Archive Extraction | Extract RAR, ZIP, 7z, tar.gz, tar.bz2 | Implemented |
| F-041 | Auto-Extraction | Extract archives automatically after download | Implemented |
| F-042 | Multi-Volume Archives | Support split archive extraction | Implemented |
| F-043 | Custom Extract Path | Configure extraction destination | Implemented |
| F-044 | File Validation | Checksum verification (MD5, SHA256, SHA1) | Implemented |
| F-045 | Auto-Validation | Validate files automatically after download | Implemented |

### 4.6 File Management Features

| ID | Feature | Description | Status |
|----|---------|-------------|--------|
| F-050 | Delete Local File | Remove downloaded files | Implemented |
| F-051 | Delete Remote File | Remove source files via SFTP | Implemented |
| F-052 | Bulk Operations | Queue/stop/delete multiple files | Implemented |

### 4.7 UI Features

| ID | Feature | Description | Status |
|----|---------|-------------|--------|
| F-060 | Real-Time Dashboard | Live file list with SSE updates | Implemented |
| F-061 | File Filtering | Filter by name and status | Implemented |
| F-062 | File Sorting | Sort by name, status, size | Implemented |
| F-063 | Filter Persistence | Pin filters across sessions | Implemented |
| F-064 | Dark Mode | Light/dark theme toggle | Implemented |
| F-065 | Expandable Details | Show/hide detailed file info | Implemented |
| F-066 | Toast Notifications | User feedback for actions | Implemented |

### 4.8 Logging & Monitoring Features

| ID | Feature | Description | Status |
|----|---------|-------------|--------|
| F-070 | Real-Time Log Streaming | Live log display via SSE | Implemented |
| F-071 | Log Level Filtering | Filter by severity | Implemented |
| F-072 | Log Search | Text search in logs | Implemented |
| F-073 | Connection Status | SSE connection indicator | Implemented |

### 4.9 Server Management Features

| ID | Feature | Description | Status |
|----|---------|-------------|--------|
| F-080 | Graceful Restart | Restart service without data loss | Implemented |
| F-081 | Configuration API | REST API for all settings | Implemented |
| F-082 | Update Checking | Check for new versions | Implemented |
| F-083 | Self-Update | Download and install updates | Implemented |

### 4.10 Connection Features

| ID | Feature | Description | Status |
|----|---------|-------------|--------|
| F-090 | SSH Password Auth | Connect using password | Implemented |
| F-091 | SSH Key Auth | Connect using private key | Implemented |
| F-092 | Custom SSH Port | Configure non-standard port | Implemented |
| F-093 | Connection Limits | Configure max connections | Implemented |
| F-094 | Bandwidth Limiting | Throttle download speed | Implemented |

---

## 5. System Architecture

### 5.1 High-Level Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                              User                                       │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         Angular Frontend                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐     │
│  │Dashboard │ │ Settings │ │AutoQueue │ │   Logs   │ │  About   │     │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘     │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Services Layer                                │   │
│  │  FileModelService, ConfigService, PathPairService, LogService   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                        ┌───────────┴───────────┐
                        │ REST API │    SSE     │
                        └───────────┬───────────┘
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         Python Backend                                  │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     Web Layer (Flask)                            │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │   │
│  │  │ Config  │ │Commands │ │PathPairs│ │ Mounts  │ │ Stream  │   │   │
│  │  │ Handler │ │ Handler │ │ Handler │ │ Handler │ │ Handler │   │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                    │                                    │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Controller Layer                              │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                │   │
│  │  │   Scanner   │ │  Downloader │ │  Processor  │                │   │
│  │  │   Manager   │ │   Manager   │ │   Manager   │                │   │
│  │  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘                │   │
│  │         │               │               │                        │   │
│  │         ▼               ▼               ▼                        │   │
│  │  ┌───────────┐   ┌───────────┐   ┌───────────┐                  │   │
│  │  │  Remote   │   │   LFTP    │   │  Extract  │                  │   │
│  │  │  Scanner  │   │  Process  │   │  Process  │                  │   │
│  │  └───────────┘   └───────────┘   └───────────┘                  │   │
│  │  ┌───────────┐                   ┌───────────┐                  │   │
│  │  │   Local   │                   │ Validate  │                  │   │
│  │  │  Scanner  │                   │  Process  │                  │   │
│  │  └───────────┘                   └───────────┘                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Data Layer                                    │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                │   │
│  │  │   Config    │ │  PathPairs  │ │   Mounts    │                │   │
│  │  │  (YAML)     │ │  (Pickle)   │ │  (Pickle)   │                │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
            ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
            │   Remote    │ │    Local    │ │   Network   │
            │   Server    │ │   Storage   │ │   Mounts    │
            │   (SSH)     │ │             │ │  (NFS/SMB)  │
            └─────────────┘ └─────────────┘ └─────────────┘
```

### 5.2 Process Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     RapidCopy Main Process                       │
│                                                                  │
│  ┌──────────────────────┐    ┌──────────────────────┐           │
│  │   Controller Thread  │    │    Web App Thread    │           │
│  │                      │    │                      │           │
│  │  - Command Queue     │◄──►│  - REST API          │           │
│  │  - State Machine     │    │  - SSE Streaming     │           │
│  │  - Job Coordination  │    │  - Static Files      │           │
│  └──────────┬───────────┘    └──────────────────────┘           │
│             │                                                    │
│             ▼                                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                 Worker Process Pool                       │   │
│  │                                                           │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │   │
│  │  │ Remote   │ │ Local    │ │ Download │ │ Extract  │    │   │
│  │  │ Scanner  │ │ Scanner  │ │ Scanner  │ │ Worker   │    │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘    │   │
│  │                                                           │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                  │   │
│  │  │ Validate │ │ Delete   │ │ Delete   │                  │   │
│  │  │ Worker   │ │ Local    │ │ Remote   │                  │   │
│  │  └──────────┘ └──────────┘ └──────────┘                  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   LFTP Subprocesses                       │   │
│  │                                                           │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                  │   │
│  │  │ Download │ │ Download │ │ Download │  (configurable)  │   │
│  │  │  Slot 1  │ │  Slot 2  │ │  Slot N  │                  │   │
│  │  └──────────┘ └──────────┘ └──────────┘                  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. API Surface

### 6.1 REST Endpoints Summary

| Category | Endpoints | Methods |
|----------|-----------|---------|
| Server Status | `/server/status`, `/server/stream` | GET |
| File Commands | `/server/command/{action}/{file}` | GET |
| Configuration | `/server/config/get`, `/server/config/set` | GET, POST |
| Path Pairs | `/server/pathpairs` | GET, POST, PUT, DELETE |
| Network Mounts | `/server/mounts`, `/server/mounts/{id}/{action}` | GET, POST, PUT, DELETE |
| Auto-Queue | `/server/autoqueue` | GET, POST, PUT, DELETE |
| Updates | `/server/update/latest`, `/server/update/download` | GET |
| Server Control | `/server/restart` | POST |

### 6.2 SSE Event Types

| Event | Payload | Description |
|-------|---------|-------------|
| `model-init` | `{files: [...]}` | Initial file list on connect |
| `model-added` | `{file: {...}}` | New file discovered |
| `model-updated` | `{file: {...}}` | File state/progress changed |
| `model-removed` | `{name: "..."}` | File removed |
| `status` | `{connected: bool, ...}` | Server status update |
| `log-record` | `{level, message, timestamp}` | Log entry |

---

## 7. Data Models

### 7.1 File States

```
                                ┌─────────┐
                                │ DEFAULT │ (discovered)
                                └────┬────┘
                                     │ queue
                                     ▼
                                ┌─────────┐
                      ┌─────────│ QUEUED  │─────────┐
                      │         └────┬────┘         │
                      │ stop         │ start        │ delete
                      ▼              ▼              ▼
                 ┌─────────┐   ┌───────────┐   ┌─────────┐
                 │ STOPPED │   │DOWNLOADING│   │ DELETED │
                 └────┬────┘   └─────┬─────┘   └─────────┘
                      │              │
                      │ retry        │ complete
                      │              ▼
                      │         ┌───────────┐
                      └────────►│DOWNLOADED │
                                └─────┬─────┘
                          ┌───────────┼───────────┐
                          │ extract   │ validate  │
                          ▼           │           ▼
                    ┌───────────┐     │     ┌───────────┐
                    │EXTRACTING │     │     │VALIDATING │
                    └─────┬─────┘     │     └─────┬─────┘
                          │           │           │
                          ▼           │     ┌─────┴─────┐
                    ┌───────────┐     │     ▼           ▼
                    │ EXTRACTED │     │ ┌─────────┐ ┌─────────┐
                    └───────────┘     │ │VALIDATED│ │ CORRUPT │
                                      │ └─────────┘ └─────────┘
                                      │
                                      ▼
                                 (final state)
```

### 7.2 Core Entities

| Entity | Description | Persistence |
|--------|-------------|-------------|
| ModelFile | File with state, size, progress | In-memory |
| PathPair | Remote/local path mapping | Pickle file |
| NetworkMount | NFS/SMB mount configuration | Pickle file |
| AutoQueuePattern | Regex pattern for auto-queue | Pickle file |
| Config | Application settings | YAML file |

---

## 8. Configuration Options

### 8.1 Connection Settings

| Setting | Type | Description |
|---------|------|-------------|
| `remote_address` | string | SSH server hostname/IP |
| `remote_username` | string | SSH username |
| `remote_password` | string | SSH password (optional) |
| `remote_port` | integer | SSH port (default: 22) |
| `use_ssh_key` | boolean | Use key authentication |

### 8.2 Download Settings

| Setting | Type | Description |
|---------|------|-------------|
| `num_max_parallel_downloads` | integer | Concurrent download slots |
| `num_max_connections_per_file` | integer | Segments per file |
| `num_max_total_connections` | integer | Total connection limit |
| `rate_limit` | string | Bandwidth limit (e.g., "10M") |
| `use_temp_file` | boolean | Download to .lftp temp file |

### 8.3 Scan Settings

| Setting | Type | Description |
|---------|------|-------------|
| `interval_ms_remote_scan` | integer | Remote scan interval (ms) |
| `interval_ms_local_scan` | integer | Local scan interval (ms) |
| `interval_ms_downloading_scan` | integer | Progress update interval (ms) |

### 8.4 Post-Processing Settings

| Setting | Type | Description |
|---------|------|-------------|
| `auto_extract` | boolean | Extract archives automatically |
| `extract_path` | string | Custom extraction destination |
| `auto_validate` | boolean | Validate files automatically |
| `validation_algorithm` | string | Hash algorithm (md5/sha256) |

---

## 9. Non-Functional Requirements

### 9.1 Performance

| Metric | Target |
|--------|--------|
| UI responsiveness | < 100ms for user actions |
| SSE latency | < 500ms for updates |
| Memory usage | < 500MB under normal load |
| File list capacity | 10,000+ files supported |

### 9.2 Reliability

| Requirement | Description |
|-------------|-------------|
| Graceful restart | No data loss on restart |
| Connection resilience | Auto-reconnect on network issues |
| Download resume | Resume from partial downloads |
| Config backup | Persist all configuration |

### 9.3 Security

| Requirement | Description |
|-------------|-------------|
| SSH key support | Passwordless authentication |
| Credential storage | Secure storage for SMB passwords |
| No auth bypass | All API endpoints validated |

### 9.4 Deployment

| Platform | Support |
|----------|---------|
| Docker | Primary deployment method |
| Linux native | .deb packages |
| ARM | arm64, arm/v7 support |
| macOS/Windows | Via Docker |

---

## Appendix A: Feature Dependencies

```
Network Mounts ──► Path Pairs ──► File Discovery ──► Download Queue
                                                            │
                                                            ▼
                                                     File Download
                                                            │
                                              ┌─────────────┼─────────────┐
                                              ▼             ▼             ▼
                                         Extraction    Validation    Deletion
```

## Appendix B: Technology Dependencies

| Component | Technology | Purpose |
|-----------|------------|---------|
| File Transfer | LFTP | High-performance SFTP downloads |
| Archive Extraction | 7z, unrar | Extract compressed archives |
| Web Server | Flask | REST API and SSE streaming |
| Frontend | Angular 18 | Single-page application |
| UI Components | PrimeNG | Rich UI component library |
| Containerization | Docker | Deployment and isolation |
| Network Mounts | nfs-common, cifs-utils | Mount NFS/SMB shares |

---

*Document Version: 1.0*
*Generated: 2025-02-14*
