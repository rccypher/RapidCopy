import {Record} from "immutable";

/**
 * View file
 * Represents the View Model
 */
interface IViewFile {
    name: string;
    isDir: boolean;
    localSize: number;
    remoteSize: number;
    percentDownloaded: number;
    status: ViewFile.Status;
    downloadingSpeed: number;
    eta: number;
    fullPath: string;
    isArchive: boolean;  // corresponds to is_extractable in ModelFile
    isSelected: boolean;
    isQueueable: boolean;
    isStoppable: boolean;
    // whether file can be queued for extraction (independent of isArchive)
    isExtractable: boolean;
    isLocallyDeletable: boolean;
    isRemotelyDeletable: boolean;
    // timestamps
    localCreatedTimestamp: Date;
    localModifiedTimestamp: Date;
    remoteCreatedTimestamp: Date;
    remoteModifiedTimestamp: Date;
    // path pair info
    pathPairId: string;
    pathPairName: string;
}

// Boiler plate code to set up an immutable class
const DefaultViewFile: IViewFile = {
    name: null,
    isDir: null,
    localSize: null,
    remoteSize: null,
    percentDownloaded: null,
    status: null,
    downloadingSpeed: null,
    eta: null,
    fullPath: null,
    isArchive: null,
    isSelected: null,
    isQueueable: null,
    isStoppable: null,
    isExtractable: null,
    isLocallyDeletable: null,
    isRemotelyDeletable: null,
    localCreatedTimestamp: null,
    localModifiedTimestamp: null,
    remoteCreatedTimestamp: null,
    remoteModifiedTimestamp: null,
    pathPairId: null,
    pathPairName: null
};
const ViewFileRecord = Record(DefaultViewFile);

/**
 * Immutable class that implements the interface
 * Note: Using getters to properly access Record values in Immutable.js 4.x
 */
export class ViewFile extends ViewFileRecord implements IViewFile {
    constructor(props) {
        super(props);
    }

    // Use getters to properly access Record values (Immutable.js 4.x compatibility)
    get name(): string { return this.get("name"); }
    get isDir(): boolean { return this.get("isDir"); }
    get localSize(): number { return this.get("localSize"); }
    get remoteSize(): number { return this.get("remoteSize"); }
    get percentDownloaded(): number { return this.get("percentDownloaded"); }
    get status(): ViewFile.Status { return this.get("status"); }
    get downloadingSpeed(): number { return this.get("downloadingSpeed"); }
    get eta(): number { return this.get("eta"); }
    get fullPath(): string { return this.get("fullPath"); }
    get isArchive(): boolean { return this.get("isArchive"); }
    get isSelected(): boolean { return this.get("isSelected"); }
    get isQueueable(): boolean { return this.get("isQueueable"); }
    get isStoppable(): boolean { return this.get("isStoppable"); }
    get isExtractable(): boolean { return this.get("isExtractable"); }
    get isLocallyDeletable(): boolean { return this.get("isLocallyDeletable"); }
    get isRemotelyDeletable(): boolean { return this.get("isRemotelyDeletable"); }
    get localCreatedTimestamp(): Date { return this.get("localCreatedTimestamp"); }
    get localModifiedTimestamp(): Date { return this.get("localModifiedTimestamp"); }
    get remoteCreatedTimestamp(): Date { return this.get("remoteCreatedTimestamp"); }
    get remoteModifiedTimestamp(): Date { return this.get("remoteModifiedTimestamp"); }
    get pathPairId(): string { return this.get("pathPairId"); }
    get pathPairName(): string { return this.get("pathPairName"); }
}

export module ViewFile {
    export enum Status {
        DEFAULT         = <any> "default",
        QUEUED          = <any> "queued",
        DOWNLOADING     = <any> "downloading",
        DOWNLOADED      = <any> "downloaded",
        STOPPED         = <any> "stopped",
        DELETED         = <any> "deleted",
        EXTRACTING      = <any> "extracting",
        EXTRACTED       = <any> "extracted"
    }
}
