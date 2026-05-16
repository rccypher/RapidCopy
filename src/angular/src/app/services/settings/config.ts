import {Record} from "immutable";

/**
 * Backend config
 * Note: Naming convention matches that used in the JSON
 */

/*
 * GENERAL
 */
interface IGeneral {
    debug: boolean;
}
const DefaultGeneral: IGeneral = {
    debug: null
};
const GeneralRecord = Record(DefaultGeneral);

/*
 * LFTP
 */
interface ILftp {
    remote_address: string;
    remote_username: string;
    remote_password: string;
    remote_port: number;
    remote_path: string;
    local_path: string;
    remote_path_to_scan_script: string;
    use_ssh_key: boolean;
    num_max_parallel_downloads: number;
    num_max_parallel_files_per_download: number;
    num_max_connections_per_root_file: number;
    num_max_connections_per_dir_file: number;
    num_max_total_connections: number;
    use_temp_file: boolean;
}
const DefaultLftp: ILftp = {
    remote_address: null,
    remote_username: null,
    remote_password: null,
    remote_port: null,
    remote_path: null,
    local_path: null,
    remote_path_to_scan_script: null,
    use_ssh_key: null,
    num_max_parallel_downloads: null,
    num_max_parallel_files_per_download: null,
    num_max_connections_per_root_file: null,
    num_max_connections_per_dir_file: null,
    num_max_total_connections: null,
    use_temp_file: null,
};
const LftpRecord = Record(DefaultLftp);

/*
 * CONTROLLER
 */
interface IController {
    interval_ms_remote_scan: number;
    interval_ms_local_scan: number;
    interval_ms_downloading_scan: number;
    extract_path: string;
    use_local_path_as_extract_path: boolean;
    enable_download_validation: boolean;
    download_validation_max_retries: number;
    use_chunked_validation: boolean;
    validation_chunk_size_mb: number;
    enable_disk_space_check: boolean;
    disk_space_min_percent: number;
}
const DefaultController: IController = {
    interval_ms_remote_scan: null,
    interval_ms_local_scan: null,
    interval_ms_downloading_scan: null,
    extract_path: null,
    use_local_path_as_extract_path: null,
    enable_download_validation: null,
    download_validation_max_retries: null,
    use_chunked_validation: null,
    validation_chunk_size_mb: null,
    enable_disk_space_check: null,
    disk_space_min_percent: null,
};
const ControllerRecord = Record(DefaultController);

/*
 * WEB
 */
interface IWeb {
    port: number;
}
const DefaultWeb: IWeb = {
    port: null
};
const WebRecord = Record(DefaultWeb);

/*
 * AUTOQUEUE
 */
interface IAutoQueue {
    enabled: boolean;
    patterns_only: boolean;
    auto_extract: boolean;
}
const DefaultAutoQueue: IAutoQueue = {
    enabled: null,
    patterns_only: null,
    auto_extract: null,
};
const AutoQueueRecord = Record(DefaultAutoQueue);



/*
 * PATHMAPPINGS
 */
interface IPathMappings {
    mappings_json: string;
}
const DefaultPathMappings: IPathMappings = {
    mappings_json: null,
};
const PathMappingsRecord = Record(DefaultPathMappings);

/*
 * CONFIG
 */
export interface IConfig {
    general: IGeneral;
    lftp: ILftp;
    controller: IController;
    web: IWeb;
    autoqueue: IAutoQueue;
    pathmappings: IPathMappings;
}
const DefaultConfig: IConfig = {
    general: null,
    lftp: null,
    controller: null,
    web: null,
    autoqueue: null,
    pathmappings: null,
};
const ConfigRecord = Record(DefaultConfig);


export class Config extends ConfigRecord implements IConfig {
    general: IGeneral;
    lftp: ILftp;
    controller: IController;
    web: IWeb;
    autoqueue: IAutoQueue;
    pathmappings: IPathMappings;

    constructor(props) {
        // Create immutable members
        super({
            general: GeneralRecord(props.general),
            lftp: LftpRecord(props.lftp),
            controller: ControllerRecord(props.controller),
            web: WebRecord(props.web),
            autoqueue: AutoQueueRecord(props.autoqueue),
            pathmappings: PathMappingsRecord(props.pathmappings)
        });
    }
}
