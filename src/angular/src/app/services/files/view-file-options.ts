import {Record} from "immutable";

import {ViewFile} from "./view-file";

/**
 * View file options
 * Describes display related options for view files
 */
interface IViewFileOptions {
    // Show additional details about the view file
    showDetails: boolean;

    // Method to use to sort the view file list
    sortMethod: ViewFileOptions.SortMethod;

    // Status filter setting
    selectedStatusFilter: ViewFile.Status;

    // Name filter setting
    nameFilter: string;

    // Track filter pin status
    pinFilter: boolean;
}


// Boiler plate code to set up an immutable class
const DefaultViewFileOptions: IViewFileOptions = {
    showDetails: null,
    sortMethod: null,
    selectedStatusFilter: null,
    nameFilter: null,
    pinFilter: null,
};
const ViewFileOptionsRecord = Record(DefaultViewFileOptions);


/**
 * Immutable class that implements the interface
 * Note: Using getters to properly access Record values in Immutable.js 4.x
 */
export class ViewFileOptions extends ViewFileOptionsRecord implements IViewFileOptions {
    constructor(props) {
        super(props);
    }

    // Use getters to properly access Record values (Immutable.js 4.x compatibility)
    get showDetails(): boolean {
        return this.get("showDetails");
    }

    get sortMethod(): ViewFileOptions.SortMethod {
        return this.get("sortMethod");
    }

    get selectedStatusFilter(): ViewFile.Status {
        return this.get("selectedStatusFilter");
    }

    get nameFilter(): string {
        return this.get("nameFilter");
    }

    get pinFilter(): boolean {
        return this.get("pinFilter");
    }
}

export module ViewFileOptions {
    export enum SortMethod {
        STATUS,
        NAME_ASC,
        NAME_DESC,
        SIZE_ASC,
        SIZE_DESC,
        SPEED_DESC,
        ETA_ASC
    }
}
