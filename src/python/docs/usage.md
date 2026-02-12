# Usage

## Dashboard

The Dashboard page shows all the files and directories on the remote server and the local machine.
Here you can manually queue files to be transferred, extract archives and delete files.

### Path Pair Badges

When multiple path pairs are configured, each file in the Dashboard displays a **path pair badge** showing which path pair it belongs to. This helps you quickly identify where files are located and where they will be downloaded to.

- The badge shows the **name** of the path pair (e.g., "Movies", "TV Shows")
- Clicking on a file shows its full remote and local paths
- Downloads are automatically routed to the correct local directory based on the path pair

## Multiple Path Pairs

RapidCopy supports syncing multiple remote/local directory combinations in a single instance. This is useful when you have:

- Multiple content types on your remote server (movies, TV shows, music)
- Different source directories that should sync to different local destinations
- Content that should have different auto-queue behaviors

### How Path Pairs Work

1. **Independent Scanning** - Each path pair is scanned separately for new and changed files
2. **Path Pair Tagging** - Files are tagged with their path pair ID and name
3. **Automatic Routing** - Downloads go to the correct local directory based on the path pair
4. **Selective Auto-Queue** - Each path pair can have auto-queue enabled or disabled independently

### Configuring Path Pairs

Path pairs are configured in `path_pairs.json` in your config directory. See the [Deployment Guide](../../../docs/DEPLOYMENT.md#multi-path-configuration) for detailed setup instructions.

Example configuration:

```json
{
  "version": 1,
  "path_pairs": [
    {
      "id": "movies-001",
      "name": "Movies",
      "remote_path": "/seedbox/movies",
      "local_path": "/downloads/movies",
      "enabled": true,
      "auto_queue": true
    },
    {
      "id": "tvshows-002",
      "name": "TV Shows",
      "remote_path": "/seedbox/tv",
      "local_path": "/downloads/tv",
      "enabled": true,
      "auto_queue": false
    }
  ]
}
```

### Path Pair Fields

| Field | Description |
|-------|-------------|
| `id` | Unique identifier for the path pair |
| `name` | Human-readable name displayed in the UI |
| `remote_path` | Directory on the remote server to scan |
| `local_path` | Local destination for downloads |
| `enabled` | Set to `false` to temporarily disable this path pair |
| `auto_queue` | Automatically queue new files from this path pair |

### Tips for Multiple Path Pairs

- **Use descriptive names** - The name appears in the UI badge, so make it clear and concise
- **Disable auto-queue selectively** - You might want auto-queue for TV shows but manual selection for movies
- **Temporarily disable pairs** - Set `enabled: false` to stop scanning a path pair without removing it

## AutoQueue

AutoQueue queues all newly discovered files on the remote server.
You can also restrict AutoQueue to pattern-based matches (see this option in the Settings page).
When pattern restriction is enabled, the AutoQueue page is where you can add or remove patterns.
Any files or directories on the remote server that match a pattern will be automatically queued for transfer.

### AutoQueue with Multiple Path Pairs

When using multiple path pairs, auto-queue behavior is controlled **per path pair**:

- Set `auto_queue: true` in a path pair to automatically queue all new files from that remote path
- Set `auto_queue: false` to require manual selection for files in that path pair
- Pattern-based matching (from the Settings page) applies across all path pairs with auto-queue enabled

## Dark Mode

RapidCopy includes a dark mode for comfortable viewing in low-light environments.

- **Toggle location** - Click the theme toggle in the sidebar
- **Automatic persistence** - Your preference is saved and restored on reload
- **Full coverage** - All UI elements support dark mode

