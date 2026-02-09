# Multi-Path Mapping Feature Implementation Plan

## Overview

Add support for multiple remote/local directory path mappings, allowing SeedSync
to download from multiple remote server directories to corresponding local directories.

Example: Remote `/data/tv_shows` -> Local `/downloads/tv_shows` AND
Remote `/data/movies` -> Local `/downloads/movies`.

Currently, SeedSync supports only a single `remote_path` / `local_path` pair
configured in the `[Lftp]` config section.

---

## Architecture Summary

### Current Flow
```
Config (single remote_path, local_path)
  ├── LFTP module: set_base_remote_dir_path() / set_base_local_dir_path()
  ├── RemoteScanner: scans single remote_path via SSH
  ├── LocalScanner: scans single local_path on filesystem
  ├── ActiveScanner: scans single local_path for active downloads
  ├── ModelBuilder: merges remote + local + lftp into unified Model
  ├── ValidateProcess: compares files at remote_path vs local_path
  ├── DeleteLocalProcess: deletes from local_path
  ├── DeleteRemoteProcess: deletes from remote_path via SSH
  ├── ExtractDispatch: extracts archives from local_path
  └── Web API / Angular UI: displays single path pair in settings
```

### Target Flow
```
Config (list of PathMapping objects, each with remote_path + local_path)
  ├── LFTP module: queue() takes explicit remote/local paths per file
  ├── RemoteScanner[]: one per path mapping, scans its remote_path
  ├── LocalScanner[]: one per path mapping, scans its local_path
  ├── ActiveScanner[]: one per path mapping, scans its local_path
  ├── ModelBuilder: merges files from ALL scanners, tags each with mapping_index
  ├── ModelFile: carries mapping_index so operations know which paths to use
  ├── ValidateProcess: uses file's mapping to get correct remote/local paths
  ├── DeleteLocalProcess: uses file's mapping for correct local_path
  ├── DeleteRemoteProcess: uses file's mapping for correct remote_path
  ├── ExtractDispatch: uses file's mapping for correct local_path
  └── Web API / Angular UI: dynamic list of path mappings in settings
```

---

## Implementation Steps

### Step 1: Python Config - Add PathMappings

**File: `src/python/common/config.py`**

Add a new `PathMapping` data class and modify config to support a list of them.

The INI config system uses fixed properties per section. To support dynamic lists,
add a new `PathMappings` section with indexed entries:

```ini
[PathMappings]
num_mappings = 2
1_remote_path = /data/tv_shows
1_local_path = /downloads/tv_shows
2_remote_path = /data/movies
2_local_path = /downloads/movies
```

**Changes needed:**

1. Create a `PathMapping` dataclass (not InnerConfig - it's a simple pair):
   ```python
   class PathMapping:
       def __init__(self, remote_path: str, local_path: str):
           self.remote_path = remote_path
           self.local_path = local_path
   ```

2. Create a `Config.PathMappings` InnerConfig section with a custom `from_dict`/`as_dict`
   that handles the indexed property pattern. This is the trickiest part because
   `InnerConfig.from_dict()` expects fixed property names.

   **Alternative approach (simpler):** Store as a JSON string in a single property:
   ```ini
   [PathMappings]
   mappings_json = [{"remote_path": "/data/tv", "local_path": "/dl/tv"}, ...]
   ```
   This avoids fighting the INI/InnerConfig system.

3. Add `self.path_mappings` to `Config.__init__()` (line 308-313)
4. Add parsing in `Config.from_dict()` (line 363-374)
5. Add serialization in `Config.as_dict()` (line 376-385)

**Backward compatibility:** If `[PathMappings]` section is missing, auto-create it
from the existing `lftp.remote_path` and `lftp.local_path` values. Keep the old
properties for now so existing config files don't break on parse.

**File: `src/python/seedsync.py`**

- Add default path mappings in `_create_default_config()` (around line 290)
- In `_check_incomplete_config()`, check for at least one valid path mapping

---

### Step 2: Add mapping_index to ModelFile

**File: `src/python/model/file.py`** (lines 10-246)

Add a `mapping_index` property to `ModelFile`:
```python
# In __init__ (line 29):
self.__mapping_index = None  # index into PathMappings list

# New property (after line 245):
@property
def mapping_index(self) -> Optional[int]: return self.__mapping_index

@mapping_index.setter
def mapping_index(self, idx: Optional[int]):
    self.__mapping_index = idx
```

Exclude `mapping_index` from `__eq__` comparison (add to line 54 exclusion set):
```python
"_ModelFile__mapping_index"
```

**File: `src/python/web/serialize/serialize_model.py`** (lines 38-108)

Add serialization for `mapping_index`:
- Add `__KEY_FILE_MAPPING_INDEX = "mapping_index"` (after line 61)
- Add to `__model_file_to_json_dict()` (after line 83):
  ```python
  json_dict[SerializeModel.__KEY_FILE_MAPPING_INDEX] = model_file.mapping_index
  ```

**File: `src/angular/src/app/services/files/model-file.ts`** (lines 7-110)

Add `mapping_index` to the Angular model:
- Add to `IModelFile` interface: `mapping_index: number;`
- Add to `DefaultModelFile`: `mapping_index: null`

---

### Step 3: Scanners - One Per Path Mapping

**File: `src/python/controller/scan/remote_scanner.py`** (lines 30-138)

No changes needed to RemoteScanner itself - it already takes `remote_path_to_scan`
as a constructor parameter. The Controller will just create multiple instances.

**File: `src/python/controller/scan/local_scanner.py`**

No changes needed - already takes `local_path` as constructor parameter.

**File: `src/python/controller/scan/active_scanner.py`**

No changes needed - already takes `local_path` as constructor parameter.

**File: `src/python/controller/scan/scanner_process.py`**

No changes needed - already wraps a single scanner instance.

---

### Step 4: ModelBuilder - Merge Multiple Scan Sources

**File: `src/python/controller/model_builder.py`** (lines 16-377)

This is the most complex change. Currently, ModelBuilder receives one set of
remote_files and one set of local_files. It needs to receive multiple sets, one
per path mapping, and tag each ModelFile with its `mapping_index`.

**Key changes:**

1. Change data structures from single dict to list of dicts:
   ```python
   # Before:
   self.__local_files = dict()   # {name: SystemFile}
   self.__remote_files = dict()  # {name: SystemFile}

   # After:
   self.__local_files_by_mapping = []    # [dict(), dict(), ...]
   self.__remote_files_by_mapping = []   # [dict(), dict(), ...]
   ```

2. Change setter methods:
   ```python
   # Before:
   def set_remote_files(self, remote_files: List[SystemFile])

   # After:
   def set_remote_files(self, mapping_index: int, remote_files: List[SystemFile])
   ```

3. In `build_model()` (line 130):
   - Iterate over each mapping_index
   - For each mapping, merge its remote_files + local_files + lftp_statuses
   - Set `model_file.mapping_index = mapping_index` for each file
   - **Handle file name conflicts**: If the same file name exists in multiple
     mappings, prefix with mapping label or raise an error. Since each mapping
     scans different directories, names COULD overlap (e.g., both have "file.txt").
     **Decision needed:** Use `mapping_index:filename` as the key, or ensure names
     are unique by prefixing with the mapping's remote_path basename.

   **Recommended approach:** Prefix file names with a mapping label to avoid
   collisions. E.g., files from mapping 0 (tv_shows) become `[tv_shows]/file.mkv`.
   Or simpler: just use the remote_path's last directory name as a virtual folder.

   **Alternative approach (simpler):** Since each mapping is a different directory,
   just show files from all mappings in a flat list. If names collide, show them
   with their mapping label. This is simpler but may confuse users.

   **Best approach:** Create a virtual root folder per mapping, named after the
   remote_path. E.g., mapping for `/data/tv_shows` creates a virtual `tv_shows/`
   root. All files under it retain their normal names. This naturally avoids
   collisions and provides clear visual grouping.

---

### Step 5: LFTP - Per-File Path Override

**File: `src/python/lftp/lftp.py`** (lines 27-409)

Modify `queue()` method (line 333) to accept optional path overrides:

```python
# Before (line 333):
def queue(self, name: str, is_dir: bool):

# After:
def queue(self, name: str, is_dir: bool,
          remote_path: str = None, local_path: str = None):
```

In the method body (lines 347-358), use the override paths if provided,
otherwise fall back to `self.__base_remote_dir_path` / `self.__base_local_dir_path`:

```python
remote_dir = remote_path if remote_path else self.__base_remote_dir_path
local_dir = local_path if local_path else self.__base_local_dir_path
```

---

### Step 6: Controller - Orchestrate Multiple Scanners

**File: `src/python/controller/controller.py`** (lines 31-708)

This is the largest change. The controller currently creates one scanner of each
type. It needs to create one set of scanners per path mapping.

**Constructor changes (lines 77-185):**

1. Store path_mappings from config:
   ```python
   self.__path_mappings = self.__context.config.path_mappings.get_mappings()
   ```

2. Create scanner arrays (replace lines 126-154):
   ```python
   self.__remote_scanners = []  # one per mapping
   self.__local_scanners = []
   self.__active_scanners = []
   self.__remote_scan_processes = []
   self.__local_scan_processes = []
   self.__active_scan_processes = []

   for i, mapping in enumerate(self.__path_mappings):
       remote_scanner = RemoteScanner(
           remote_address=...,
           remote_path_to_scan=mapping.remote_path,
           ...
       )
       local_scanner = LocalScanner(local_path=mapping.local_path, ...)
       active_scanner = ActiveScanner(mapping.local_path)
       # Create ScannerProcess for each
       ...
   ```

3. Don't set global LFTP base paths (remove lines 114-115). Instead, pass per-file
   paths when queuing.

**__update_model() changes (lines 303-448):**

1. Pop scan results from all scanner processes:
   ```python
   for i, proc in enumerate(self.__remote_scan_processes):
       result = proc.pop_latest_result()
       if result is not None:
           self.__model_builder.set_remote_files(i, result.files)
   ```
   Same for local and active scans.

2. Update active scanner state across all active scanners.

**__start_validation() changes (lines 452-471):**

Look up the file's `mapping_index` to get the correct remote_path and local_path:
```python
mapping = self.__path_mappings[model_file.mapping_index]
process = ValidateProcess(
    local_path=mapping.local_path,
    remote_path=mapping.remote_path,
    ...
)
```

**__delete_local_and_requeue() changes (lines 541-564):**

Look up correct local_path from file's mapping_index:
```python
mapping = self.__path_mappings[mapping_index]
local_file_path = os.path.join(mapping.local_path, file_name)
```

**__process_commands() changes (lines 566-679):**

- QUEUE command (line 586): Pass per-file paths to lftp.queue():
  ```python
  mapping = self.__path_mappings[file.mapping_index]
  self.__lftp.queue(file.name, file.is_dir,
                    remote_path=mapping.remote_path,
                    local_path=mapping.local_path)
  ```

- DELETE_LOCAL command (line 632): Use file's mapping for local_path
- DELETE_REMOTE command (line 660): Use file's mapping for remote_path

**start() / exit() changes (lines 187-235):**

Start/stop all scanner processes in the arrays.

**__propagate_exceptions() changes (lines 681-691):**

Propagate from all scanner processes.

---

### Step 7: Extract - Use Per-File Paths

**File: `src/python/controller/extract/dispatch.py`** (lines 58-220)

The `ExtractDispatch` constructor takes `out_dir_path` and `local_path` (line 71).
These need to become per-file lookups.

**Option A:** Pass the path_mappings list to ExtractDispatch and look up
the mapping from the ModelFile.

**Option B:** Store local_path on ModelFile and pass it through.

**Recommended:** Pass path_mappings to ExtractDispatch. In `extract()` method
(line 110), look up paths:
```python
def extract(self, model_file: ModelFile, local_path: str, out_dir_path: str):
```

The controller calls this with the mapping-specific paths.

**File: `src/python/controller/extract/extract_process.py`**

The `ExtractProcess` wraps `ExtractDispatch`. Its `extract()` method also needs
the per-file paths. Change signature to pass them through.

---

### Step 8: Angular Config Model

**File: `src/angular/src/app/services/settings/config.ts`** (lines 1-149)

Add the PathMappings interface and record:

```typescript
interface IPathMapping {
    remote_path: string;
    local_path: string;
}

interface IPathMappings {
    mappings: IPathMapping[];
}

const DefaultPathMappings: IPathMappings = {
    mappings: null,
};
const PathMappingsRecord = Record(DefaultPathMappings);
```

Add to `IConfig` (line 114):
```typescript
path_mappings: IPathMappings;
```

Update `Config` constructor (line 139-148) to create the PathMappings record.

---

### Step 9: Angular Settings UI - Path Mappings Editor

**File: `src/angular/src/app/pages/settings/options-list.ts`**

Remove `remote_path` and `local_path` from `OPTIONS_CONTEXT_SERVER` (lines 46-55).
These will be managed by a new dedicated path mappings component.

**New file: `src/angular/src/app/pages/settings/path-mappings.component.ts`**
**New file: `src/angular/src/app/pages/settings/path-mappings.component.html`**
**New file: `src/angular/src/app/pages/settings/path-mappings.component.scss`**

Create a new component that:
- Displays a list of path mappings (remote_path <-> local_path pairs)
- Has "Add Mapping" button to add new pairs
- Has "Remove" button per mapping
- Each mapping has two text inputs (remote and local path)
- Changes are saved via the config API

**File: `src/angular/src/app/pages/settings/settings-page.component.html`**

Add the path-mappings component to the settings page (after the Server section).

**File: `src/angular/src/app/pages/settings/settings-page.component.ts`**

Import and register the new component.

**File: `src/angular/src/app/services/settings/config.service.ts`**

May need a new API method to set path mappings as a batch (since they're a list,
not individual key-value pairs).

---

### Step 10: Web API - Path Mappings Endpoints

**File: `src/python/web/handler/config_handler.py`** (or equivalent)

The existing config API serializes the entire config. If PathMappings uses the
JSON-in-a-property approach (Step 1), no API changes are needed - the existing
config GET/SET endpoints handle it transparently.

If using indexed properties, the API needs to handle the mapping between the
frontend's list representation and the INI storage format.

---

### Step 11: Backward Compatibility Migration

**File: `src/python/seedsync.py`**

When loading config:
1. If `[PathMappings]` section exists, use it
2. If not, create it from `lftp.remote_path` and `lftp.local_path`
3. Save the migrated config

This ensures existing users' configs are automatically migrated.

---

## File Change Summary

### Python Backend (must change)
| File | Change | Complexity |
|------|--------|------------|
| `src/python/common/config.py` | Add PathMappings section | Medium |
| `src/python/model/file.py` | Add mapping_index property | Low |
| `src/python/seedsync.py` | Default config, migration | Medium |
| `src/python/lftp/lftp.py` | Per-file path in queue() | Low |
| `src/python/controller/controller.py` | Multiple scanners, per-file routing | **High** |
| `src/python/controller/model_builder.py` | Multi-source merge, mapping tags | **High** |
| `src/python/controller/delete/delete_process.py` | No change (already parameterized) | None |
| `src/python/controller/extract/dispatch.py` | Per-file local_path | Low |
| `src/python/controller/extract/extract_process.py` | Pass through per-file paths | Low |
| `src/python/controller/validate/validate_process.py` | No change (already parameterized) | None |
| `src/python/controller/scan/remote_scanner.py` | No change (already parameterized) | None |
| `src/python/controller/scan/local_scanner.py` | No change (already parameterized) | None |
| `src/python/web/serialize/serialize_model.py` | Serialize mapping_index | Low |

### Angular Frontend (must change)
| File | Change | Complexity |
|------|--------|------------|
| `src/angular/src/app/services/settings/config.ts` | Add PathMappings interface | Low |
| `src/angular/src/app/services/files/model-file.ts` | Add mapping_index | Low |
| `src/angular/src/app/pages/settings/options-list.ts` | Remove path fields from Server | Low |
| `src/angular/src/app/pages/settings/path-mappings.component.*` | **New component** | **High** |
| `src/angular/src/app/pages/settings/settings-page.component.*` | Add path-mappings | Low |

### Tests (should update)
| File | Change |
|------|--------|
| `src/python/tests/unittests/test_controller/test_validate/` | Update for mapping_index |
| `src/python/tests/unittests/test_model_builder.py` | Update for multi-source |
| `src/python/tests/unittests/test_lftp/` | Update queue() signature |

---

## Key Design Decisions Needed

1. **Config storage format**: JSON-in-a-property (simpler) vs indexed INI properties
   (more INI-native). **Recommendation:** JSON string property for simplicity.

2. **File name collision handling**: What happens if two mappings have files with
   the same name? **Recommendation:** Prefix file names with mapping label (the
   last component of remote_path, e.g., "tv_shows/file.mkv").

3. **LFTP global vs per-file paths**: Remove global base paths entirely or keep
   as fallback? **Recommendation:** Keep for backward compat but override per-file.

4. **AutoQueue**: The auto_queue.py module uses file names from the model to
   queue downloads. It calls `controller.queue_command(command)` with just a
   filename. The command needs to resolve to the correct mapping. Since ModelFile
   carries mapping_index, the controller can look it up when processing the command.

5. **UI grouping**: Should the file list group files by mapping, or show a flat list?
   **Recommendation:** Group by mapping with a visual separator/header showing the
   mapping name. This gives users clear context.

---

## Suggested Implementation Order

1. Config model (Python + Angular) - establish data structures
2. ModelFile mapping_index + serialization - plumb the data through
3. ModelBuilder multi-source - core merge logic
4. LFTP per-file paths - enable correct downloads
5. Controller multi-scanner orchestration - wire everything together
6. Operations (validate/delete/extract) - route to correct paths
7. Settings UI - path mappings editor
8. Backward compatibility migration
9. Tests
