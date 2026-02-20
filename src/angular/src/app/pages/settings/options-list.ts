import {OptionType} from "./option.component";

export interface IOption {
    type: OptionType;
    label: string;
    valuePath: [string, string];
    description: string;
}
export interface IOptionsContext {
    header: string;
    id: string;
    options: IOption[];
}

export const OPTIONS_CONTEXT_SERVER: IOptionsContext = {
    header: "Server",
    id: "server",
    options: [
        {
            type: OptionType.Text,
            label: "Server Address",
            valuePath: ["lftp", "remote_address"],
            description: null
        },
        {
            type: OptionType.Text,
            label: "Server User",
            valuePath: ["lftp", "remote_username"],
            description: null
        },
        {
            type: OptionType.Password,
            label: "Server Password",
            valuePath: ["lftp", "remote_password"],
            description: null
        },
        {
            type: OptionType.Checkbox,
            label: "Use password-less key-based authentication",
            valuePath: ["lftp", "use_ssh_key"],
            description: "Mount your SSH private key to /root/.ssh/id_rsa in the container. " +
                         "The key must not have a passphrase."
        },
        {
            type: OptionType.Text,
            label: "Remote SSH Port",
            valuePath: ["lftp", "remote_port"],
            description: null,
        },
        {
            type: OptionType.Text,
            label: "Server Script Path",
            valuePath: ["lftp", "remote_path_to_scan_script"],
            description: "Where to install scanner script on remote server"
        }
    ]
};

export const OPTIONS_CONTEXT_DISCOVERY: IOptionsContext = {
    header: "File Discovery",
    id: "file-discovery",
    options: [
        {
            type: OptionType.Text,
            label: "Remote Scan Interval (ms)",
            valuePath: ["controller", "interval_ms_remote_scan"],
            description: "How often the remote server is scanned for new files"
        },
        {
            type: OptionType.Text,
            label: "Local Scan Interval (ms)",
            valuePath: ["controller", "interval_ms_local_scan"],
            description: "How often the local directory is scanned"
        },
        {
            type: OptionType.Text,
            label: "Downloading Scan Interval (ms)",
            valuePath: ["controller", "interval_ms_downloading_scan"],
            description: "How often the downloading information is updated"
        },
    ]
};

export const OPTIONS_CONTEXT_CONNECTIONS: IOptionsContext = {
    header: "Connections",
    id: "connections",
    options: [
        {
            type: OptionType.Text,
            label: "Max Parallel Downloads",
            valuePath: ["lftp", "num_max_parallel_downloads"],
            description: "How many items download in parallel.\n" +
                         "(cmd:queue-parallel)"
        },
        {
            type: OptionType.Text,
            label: "Max Total Connections",
            valuePath: ["lftp", "num_max_total_connections"],
            description: "Maximum number of connections.\n" +
                         "(net:connection-limit)"
        },
        {
            type: OptionType.Text,
            label: "Download Rate Limit",
            valuePath: ["lftp", "rate_limit"],
            description: "Limit download speed. Use '0' for unlimited, " +
                         "or specify like '1M' (1 MB/s), '500K' (500 KB/s), '10M' (10 MB/s).\n" +
                         "(net:limit-rate)"
        },
        {
            type: OptionType.Text,
            label: "Max Connections Per File (Single-File)",
            valuePath: ["lftp", "num_max_connections_per_root_file"],
            description: "Number of connections for single-file download.\n" +
                         "(pget:default-n)"
        },
        {
            type: OptionType.Text,
            label: "Max Connections Per File (Directory)",
            valuePath: ["lftp", "num_max_connections_per_dir_file"],
            description: "Number of per-file connections for directory download.\n" +
                         "(mirror:use-pget-n)"
        },
        {
            type: OptionType.Text,
            label: "Max Parallel Files (Directory)",
            valuePath: ["lftp", "num_max_parallel_files_per_download"],
            description: "Maximum number of files to fetch in parallel for single directory download.\n" +
                         "(mirror:parallel-transfer-count)"
        },
        {
            type: OptionType.Checkbox,
            label: "Rename unfinished/downloading files",
            valuePath: ["lftp", "use_temp_file"],
            description: "Unfinished and downloading files will be named *.lftp"
        },
    ]
};

export const OPTIONS_CONTEXT_OTHER: IOptionsContext = {
    header: "Other Settings",
    id: "other-settings",
    options: [
        {
            type: OptionType.Text,
            label: "Web GUI Port",
            valuePath: ["web", "port"],
            description: null
        },
        {
            type: OptionType.Text,
            label: "API Key",
            valuePath: ["web", "api_key"],
            description: "Protect the web UI with an API key. All API requests must include an " +
                         "X-Api-Key header matching this value. Leave empty to disable authentication."
        },
        {
            type: OptionType.Checkbox,
            label: "Enable Debug",
            valuePath: ["general", "debug"],
            description: "Enables debug logging (overrides Log Level to DEBUG)."
        },
        {
            type: OptionType.Text,
            label: "Log Level",
            valuePath: ["general", "log_level"],
            description: "Set logging verbosity. Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL.\n" +
                         "Default is INFO. Ignored when Debug is enabled."
        },
    ]
};

export const OPTIONS_CONTEXT_AUTOQUEUE: IOptionsContext = {
    header: "AutoQueue",
    id: "autoqueue",
    options: [
        {
            type: OptionType.Checkbox,
            label: "Enable AutoQueue",
            valuePath: ["autoqueue", "enabled"],
            description: null
        },
        {
            type: OptionType.Checkbox,
            label: "Restrict to patterns",
            valuePath: ["autoqueue", "patterns_only"],
            description: "Only autoqueue files that match a pattern"
        },
        {
            type: OptionType.Checkbox,
            label: "Enable auto extraction",
            valuePath: ["autoqueue", "auto_extract"],
            description: "Automatically extract files"
        },
    ]
};

export const OPTIONS_CONTEXT_EXTRACT: IOptionsContext = {
    header: "Archive Extraction",
    id: "extraction",
    options: [
        {
            type: OptionType.Checkbox,
            label: "Extract archives in the downloads directory",
            valuePath: ["controller", "use_local_path_as_extract_path"],
            description: null
        },
        {
            type: OptionType.Text,
            label: "Extract Path",
            valuePath: ["controller", "extract_path"],
            description: "When option above is disabled, extract archives to this directory"
        },
    ]
};

export const OPTIONS_CONTEXT_VALIDATION: IOptionsContext = {
    header: "Download Validation",
    id: "validation",
    options: [
        {
            type: OptionType.Checkbox,
            label: "Enable download validation",
            valuePath: ["validation", "enabled"],
            description: "Validate chunk checksums during download. Corrupt chunks are automatically re-downloaded."
        },
        {
            type: OptionType.Text,
            label: "Checksum Algorithm",
            valuePath: ["validation", "algorithm"],
            description: "Hash algorithm used for chunk validation. Valid values: xxh128, md5, sha256, sha1.\n" +
                         "xxh128 is fastest; sha256 is most secure."
        },
        {
            type: OptionType.Checkbox,
            label: "Enable adaptive chunk sizing",
            valuePath: ["validation", "enable_adaptive_sizing"],
            description: "Automatically adjust chunk size based on network conditions."
        },
        {
            type: OptionType.Text,
            label: "Default Chunk Size (bytes)",
            valuePath: ["validation", "default_chunk_size"],
            description: "Starting chunk size in bytes (default: 52428800 = 50 MB)."
        },
        {
            type: OptionType.Text,
            label: "Min Chunk Size (bytes)",
            valuePath: ["validation", "min_chunk_size"],
            description: "Minimum chunk size in bytes (default: 1048576 = 1 MB)."
        },
        {
            type: OptionType.Text,
            label: "Max Chunk Size (bytes)",
            valuePath: ["validation", "max_chunk_size"],
            description: "Maximum chunk size in bytes (default: 104857600 = 100 MB)."
        },
        {
            type: OptionType.Text,
            label: "Max Retries",
            valuePath: ["validation", "max_retries"],
            description: "Maximum re-download attempts for a corrupt chunk."
        },
        {
            type: OptionType.Text,
            label: "Retry Delay (ms)",
            valuePath: ["validation", "retry_delay_ms"],
            description: "Delay in milliseconds between retry attempts."
        },
    ]
};
