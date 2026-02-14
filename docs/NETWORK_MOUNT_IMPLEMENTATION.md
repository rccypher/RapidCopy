# Network Mount Implementation Plan

## Overview

Implement network mount support (NFS/SMB/CIFS) to allow the RapidCopy container to mount network drives and download files directly to NAS or shared storage.

## Status

| Phase | Description | Status |
|-------|-------------|--------|
| **C** | Docker Configuration | Completed |
| **A1-A2** | Backend Data Model & Utilities | Completed |
| **A3-A5** | REST API & Startup | Completed |
| **B1-B4** | Frontend UI | Completed |
| **D** | Path Pairs Integration | Completed |

---

## Phase C: Docker Configuration

**Status:** Completed

### Changes Required

**Dockerfile:**
- Add `nfs-common`, `cifs-utils`, `keyutils` to runtime dependencies
- Create `/mounts` directory with proper permissions

**docker-compose.yml:**
- Add `cap_add: SYS_ADMIN` for mount capabilities
- Add `security_opt: apparmor:unconfined` for mount permissions
- Add `/mounts` volume with `shared` propagation

### Files Modified
- [x] `Dockerfile`
- [x] `docker-compose.yml`

---

## Phase A1-A2: Backend Data Model & Mount Utilities

**Status:** Completed

### Files Created

**`src/python/common/network_mount.py`**
- `MountType` enum: "nfs" | "cifs" | "local"
- `MountStatus` enum: "mounted" | "unmounted" | "error" | "unknown"
- `NetworkMount` dataclass with fields:
  - `id`: Unique identifier
  - `name`: Human-readable name
  - `mount_type`: MountType enum
  - `enabled`: Auto-mount on startup
  - `server`: Server address (e.g., "192.168.1.100")
  - `share_path`: Remote share path
  - `username`: For CIFS authentication (optional)
  - `password`: Encrypted password (optional)
  - `domain`: For CIFS domain (optional)
  - `mount_options`: Additional mount options
  - `mount_point` property returning `/mounts/{id}`
  - `mount_source` property returning formatted source string
- `NetworkMountCollection` class for collection management
- `NetworkMountManager` class for persistence (JSON-based)

**`src/python/common/mount_utils.py`**
- `generate_mount_key()` - Generate or load encryption key from `/config/.mount_key`
- `encrypt_password()` / `decrypt_password()` - Fernet encryption
- `mount_share()` - Execute mount commands (NFS/CIFS)
- `unmount_share()` - Execute umount command with optional force
- `get_mount_status()` - Check if mounted via /proc/mounts
- `test_connection()` - Verify network connectivity via socket

### Files Modified
- [x] `src/python/common/__init__.py` - Export new classes

---

## Phase A3-A5: REST API & Startup Integration

**Status:** Completed

### Files Created

**`src/python/web/handler/mounts.py`**
- `MountsHandler(IHandler)` class implementing all REST endpoints:
  - `GET /server/mounts` - List all mounts with status
  - `POST /server/mounts` - Create mount
  - `PUT /server/mounts/:id` - Update mount
  - `DELETE /server/mounts/:id` - Delete mount (unmounts first if mounted)
  - `POST /server/mounts/:id/mount` - Mount share
  - `POST /server/mounts/:id/unmount` - Unmount share (supports force flag)
  - `GET /server/mounts/:id/test` - Test connection

### Files Modified
- [x] `src/python/web/web_app_builder.py` - Register MountsHandler
- [x] `src/python/rapidcopy.py` - Initialize NetworkMountManager, auto-mount enabled shares on startup via `_auto_mount_network_shares()`
- [x] `src/python/common/context.py` - Add `network_mount_manager` field

---

## Phase B1-B4: Frontend UI

**Status:** Completed

### Files Created

**`src/angular/src/app/services/settings/network-mount.service.ts`**
- `NetworkMount` interface with all mount fields
- `NetworkMountResponse` interface for API responses
- `MountActionResponse` interface for mount/unmount/test responses
- `NetworkMountResult` interface for create/update results with warnings
- `NetworkMountService` class with:
  - BehaviorSubject-based reactive state (`mounts$`)
  - All CRUD operations: `getAll()`, `getById()`, `create()`, `update()`, `delete()`
  - Mount operations: `mount()`, `unmount()`, `testConnection()`
  - Helper methods: `refresh()`, `getCurrentMounts()`, `getEnabledMounts()`, `getMountedMounts()`

**`src/angular/src/app/pages/settings/network-mounts.component.ts`**
- Standalone `NetworkMountsComponent` with full CRUD support
- Form fields for all mount configuration options
- Mount/unmount/test connection actions
- Loading states and error handling

**`src/angular/src/app/pages/settings/network-mounts.component.html`**
- Card-based list with status badges (Mounted/Unmounted/Error)
- Type badges (NFS/SMB/CIFS)
- Add/edit form with conditional CIFS-specific fields
- Mount/unmount/test buttons with loading states
- Responsive layout

**`src/angular/src/app/pages/settings/network-mounts.component.scss`**
- Consistent styling following path-pairs component patterns
- Status-based color coding
- Responsive adjustments

### Files Modified
- [x] `src/angular/src/app/pages/settings/settings-page.component.html` - Added `<app-network-mounts>` component
- [x] `src/angular/src/app/pages/settings/settings-page.component.scss` - Added `#network-mounts-section` styling
- [x] `src/angular/src/app/app.module.ts` - Imported NetworkMountsComponent and NetworkMountService

---

## Phase D: Path Pairs Integration

**Status:** Completed

### Files Modified
- [x] `src/python/common/path_pair.py` - Updated validation to recognize both `/downloads/` and `/mounts/` paths as valid in Docker:
  - Added `DOCKER_MOUNTS_BASE = "/mounts"` constant
  - Updated `PathPair.validate()` to allow paths under either `/downloads` or `/mounts`
  - Updated warning message to explain both valid path options

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    RapidCopy Container                          │
│  ┌─────────────────┐    ┌─────────────────┐                    │
│  │  Web UI         │    │  Mount Manager  │                    │
│  │  (Network Mount │───▶│  (Python)       │                    │
│  │   Settings)     │    │                 │                    │
│  └─────────────────┘    └────────┬────────┘                    │
│                                  │                              │
│                    ┌─────────────▼───────────────┐             │
│                    │  /mounts/                    │             │
│                    │  ├── nas-movies (NFS)       │             │
│                    │  ├── nas-tv (SMB)           │             │
│                    │  └── local (bind mount)     │             │
│                    └─────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Security Notes

- Passwords are encrypted using Fernet with a file-based key at `/config/.mount_key`
- The key is auto-generated on first use
- Mount operations require `SYS_ADMIN` capability (more secure than full privileged mode)
- AppArmor is disabled for the container to allow mount operations

---

## Changelog

| Date | Change |
|------|--------|
| 2025-02-14 | Initial plan created |
| 2025-02-14 | Phase C (Docker Configuration) completed |
| 2025-02-14 | Phase A1-A5 (Backend) completed |
| 2025-02-14 | Phase B1-B4 (Frontend UI) completed |
| 2025-02-14 | Phase D (Path Pairs Integration) completed |
| 2025-02-14 | **All phases completed - Feature ready for testing** |
