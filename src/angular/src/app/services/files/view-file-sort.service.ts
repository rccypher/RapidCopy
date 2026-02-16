import {Injectable} from "@angular/core";

import {LoggerService} from "../utils/logger.service";
import {ViewFile} from "./view-file";
import {ViewFileComparator, ViewFileService} from "./view-file.service";
import {ViewFileOptionsService} from "./view-file-options.service";
import {ViewFileOptions} from "./view-file-options";


/**
 * Comparator used to sort the ViewFiles
 * First, sorts by status.
 * Second, sorts by name.
 * @param {ViewFile} a
 * @param {ViewFile} b
 * @returns {number}
 * @private
 */
const StatusComparator: ViewFileComparator = (a: ViewFile, b: ViewFile): number => {
    if (a.status !== b.status) {
        const statusPriorities = {
            [ViewFile.Status.EXTRACTING]: 0,
            [ViewFile.Status.DOWNLOADING]: 1,
            [ViewFile.Status.QUEUED]: 2,
            [ViewFile.Status.EXTRACTED]: 3,
            [ViewFile.Status.DOWNLOADED]: 4,
            [ViewFile.Status.STOPPED]: 5,
            [ViewFile.Status.DEFAULT]: 6,
            [ViewFile.Status.DELETED]: 6  // intermix deleted and default
        };
        if (statusPriorities[a.status] !== statusPriorities[b.status]) {
            return statusPriorities[a.status] - statusPriorities[b.status];
        }
    }
    return a.name.localeCompare(b.name);
};

/**
 * Comparator used to sort the ViewFiles
 * Sort by name, ascending
 * @param {ViewFile} a
 * @param {ViewFile} b
 * @returns {number}
 * @constructor
 */
const NameAscendingComparator: ViewFileComparator = (a: ViewFile, b: ViewFile): number => {
    return a.name.localeCompare(b.name);
};

/**
 * Comparator used to sort the ViewFiles
 * Sort by name, descending
 * @param {ViewFile} a
 * @param {ViewFile} b
 * @returns {number}
 * @constructor
 */
const NameDescendingComparator: ViewFileComparator = (a: ViewFile, b: ViewFile): number => {
    return b.name.localeCompare(a.name);
};

/**
 * Sort by size ascending (smallest first), nulls last, then by name
 */
const SizeAscendingComparator: ViewFileComparator = (a: ViewFile, b: ViewFile): number => {
    const sizeA = a.remoteSize ?? a.localSize ?? -1;
    const sizeB = b.remoteSize ?? b.localSize ?? -1;
    if (sizeA !== sizeB) {
        if (sizeA < 0) return 1;
        if (sizeB < 0) return -1;
        return sizeA - sizeB;
    }
    return a.name.localeCompare(b.name);
};

/**
 * Sort by size descending (largest first), nulls last, then by name
 */
const SizeDescendingComparator: ViewFileComparator = (a: ViewFile, b: ViewFile): number => {
    const sizeA = a.remoteSize ?? a.localSize ?? -1;
    const sizeB = b.remoteSize ?? b.localSize ?? -1;
    if (sizeA !== sizeB) {
        if (sizeA < 0) return 1;
        if (sizeB < 0) return -1;
        return sizeB - sizeA;
    }
    return a.name.localeCompare(b.name);
};

/**
 * Sort by download speed descending (fastest first), zero/null last, then by name
 */
const SpeedDescendingComparator: ViewFileComparator = (a: ViewFile, b: ViewFile): number => {
    const speedA = a.downloadingSpeed ?? 0;
    const speedB = b.downloadingSpeed ?? 0;
    if (speedA !== speedB) {
        return speedB - speedA;
    }
    return a.name.localeCompare(b.name);
};

/**
 * Sort by ETA ascending (shortest first), zero/null last, then by name
 */
const EtaAscendingComparator: ViewFileComparator = (a: ViewFile, b: ViewFile): number => {
    const etaA = a.eta ?? 0;
    const etaB = b.eta ?? 0;
    if (etaA > 0 && etaB <= 0) return -1;
    if (etaA <= 0 && etaB > 0) return 1;
    if (etaA !== etaB) {
        return etaA - etaB;
    }
    return a.name.localeCompare(b.name);
};

/**
 * ViewFileSortService class provides sorting services for
 * view files
 *
 * This class responds to changes in the sort settings and
 * applies the appropriate comparators to the ViewFileService
 */
@Injectable()
export class ViewFileSortService {
    private _sortMethod: ViewFileOptions.SortMethod = null;

    constructor(private _logger: LoggerService,
                private _viewFileService: ViewFileService,
                private _viewFileOptionsService: ViewFileOptionsService) {
        this._viewFileOptionsService.options.subscribe(options => {
            // Check if the sort method changed
            if (this._sortMethod !== options.sortMethod) {
                this._sortMethod = options.sortMethod;
                if (this._sortMethod === ViewFileOptions.SortMethod.STATUS) {
                    this._viewFileService.setComparator(StatusComparator);
                    this._logger.debug("Comparator set to: Status");
                } else if (this._sortMethod === ViewFileOptions.SortMethod.NAME_DESC) {
                    this._viewFileService.setComparator(NameDescendingComparator);
                    this._logger.debug("Comparator set to: Name Desc");
                } else if (this._sortMethod === ViewFileOptions.SortMethod.NAME_ASC) {
                    this._viewFileService.setComparator(NameAscendingComparator);
                    this._logger.debug("Comparator set to: Name Asc");
                } else if (this._sortMethod === ViewFileOptions.SortMethod.SIZE_ASC) {
                    this._viewFileService.setComparator(SizeAscendingComparator);
                    this._logger.debug("Comparator set to: Size Asc");
                } else if (this._sortMethod === ViewFileOptions.SortMethod.SIZE_DESC) {
                    this._viewFileService.setComparator(SizeDescendingComparator);
                    this._logger.debug("Comparator set to: Size Desc");
                } else if (this._sortMethod === ViewFileOptions.SortMethod.SPEED_DESC) {
                    this._viewFileService.setComparator(SpeedDescendingComparator);
                    this._logger.debug("Comparator set to: Speed Desc");
                } else if (this._sortMethod === ViewFileOptions.SortMethod.ETA_ASC) {
                    this._viewFileService.setComparator(EtaAscendingComparator);
                    this._logger.debug("Comparator set to: ETA Asc");
                } else {
                    this._viewFileService.setComparator(null);
                    this._logger.debug("Comparator set to: null");
                }
            }
        });
    }
}
