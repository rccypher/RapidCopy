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
    verbose: boolean;
    // Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)
    log_level: string;
}
const DefaultGeneral: IGeneral = {
    debug: null,
    verbose: null,
    log_level: null
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
    // Rate limit for downloads: "0" = unlimited, or specify like "1M" (1 MB/s), "500K" (500 KB/s)
    rate_limit: string;
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
    rate_limit: null,
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
}
const DefaultController: IController = {
    interval_ms_remote_scan: null,
    interval_ms_local_scan: null,
    interval_ms_downloading_scan: null,
    extract_path: null,
    use_local_path_as_extract_path: null,
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
 * VALIDATION
 */
interface IValidation {
    enabled: boolean;
    algorithm: string;
    default_chunk_size: number;
    min_chunk_size: number;
    max_chunk_size: number;
    validate_after_chunk: boolean;
    validate_after_file: boolean;
    max_retries: number;
    retry_delay_ms: number;
    enable_adaptive_sizing: boolean;
}
const DefaultValidation: IValidation = {
    enabled: null,
    algorithm: null,
    default_chunk_size: null,
    min_chunk_size: null,
    max_chunk_size: null,
    validate_after_chunk: null,
    validate_after_file: null,
    max_retries: null,
    retry_delay_ms: null,
    enable_adaptive_sizing: null,
};
const ValidationRecord = Record(DefaultValidation);


/*
 * CONFIG
 */
export interface IConfig {
    general: IGeneral;
    lftp: ILftp;
    controller: IController;
    web: IWeb;
    autoqueue: IAutoQueue;
    validation: IValidation;
}
const DefaultConfig: IConfig = {
    general: null,
    lftp: null,
    controller: null,
    web: null,
    autoqueue: null,
    validation: null,
};
const ConfigRecord = Record(DefaultConfig);


export class Config extends ConfigRecord implements IConfig {
    constructor(props) {
        // Create immutable members
        super({
            general: GeneralRecord(props.general),
            lftp: LftpRecord(props.lftp),
            controller: ControllerRecord(props.controller),
            web: WebRecord(props.web),
            autoqueue: AutoQueueRecord(props.autoqueue),
            validation: ValidationRecord(props.validation)
        });
    }

    // Use getters to properly access Record values (Immutable.js 4.x compatibility)
    get general(): IGeneral { return this.get("general"); }
    get lftp(): ILftp { return this.get("lftp"); }
    get controller(): IController { return this.get("controller"); }
    get web(): IWeb { return this.get("web"); }
    get autoqueue(): IAutoQueue { return this.get("autoqueue"); }
    get validation(): IValidation { return this.get("validation"); }
}
