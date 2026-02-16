import {Component, ChangeDetectionStrategy, ChangeDetectorRef} from "@angular/core";
import {Observable} from "rxjs";

import {List} from "immutable";

import {ViewFileService} from "../../services/files/view-file.service";
import {ViewFile} from "../../services/files/view-file";
import {LoggerService} from "../../services/utils/logger.service";
import {ViewFileOptions} from "../../services/files/view-file-options";
import {ViewFileOptionsService} from "../../services/files/view-file-options.service";

@Component({
    selector: "app-file-list",
    providers: [],
    templateUrl: "./file-list.component.html",
    styleUrls: ["./file-list.component.scss"],
    changeDetection: ChangeDetectionStrategy.OnPush
})

export class FileListComponent {
    public files: Observable<List<ViewFile>>;
    public identify = FileListComponent.identify;
    public options: Observable<ViewFileOptions>;

    // Column header sort state
    public activeSortColumn: string = null;
    public sortAscending = true;

    // Maps column names to their sort method(s)
    private static readonly COLUMN_SORT_MAP: Record<string, {asc: ViewFileOptions.SortMethod, desc: ViewFileOptions.SortMethod}> = {
        name:   {asc: ViewFileOptions.SortMethod.NAME_ASC,   desc: ViewFileOptions.SortMethod.NAME_DESC},
        status: {asc: ViewFileOptions.SortMethod.STATUS,     desc: ViewFileOptions.SortMethod.STATUS},
        speed:  {asc: ViewFileOptions.SortMethod.SPEED_DESC, desc: ViewFileOptions.SortMethod.SPEED_DESC},
        eta:    {asc: ViewFileOptions.SortMethod.ETA_ASC,    desc: ViewFileOptions.SortMethod.ETA_ASC},
        size:   {asc: ViewFileOptions.SortMethod.SIZE_ASC,   desc: ViewFileOptions.SortMethod.SIZE_DESC},
    };

    constructor(private _logger: LoggerService,
                private viewFileService: ViewFileService,
                private viewFileOptionsService: ViewFileOptionsService,
                private _changeDetector: ChangeDetectorRef) {
        this.files = viewFileService.filteredFiles;
        this.options = this.viewFileOptionsService.options;
    }

    onHeaderSort(column: string): void {
        const mapping = FileListComponent.COLUMN_SORT_MAP[column];
        if (!mapping) return;

        if (this.activeSortColumn === column) {
            // Toggle direction if same column clicked again (only for columns with two directions)
            if (mapping.asc !== mapping.desc) {
                this.sortAscending = !this.sortAscending;
            }
        } else {
            // New column: default to ascending
            this.activeSortColumn = column;
            this.sortAscending = true;
        }

        const sortMethod = this.sortAscending ? mapping.asc : mapping.desc;
        this.viewFileOptionsService.setSortMethod(sortMethod);
        this._changeDetector.markForCheck();
    }

    // noinspection JSUnusedLocalSymbols
    /**
     * Used for trackBy in ngFor
     * @param index
     * @param item
     */
    static identify(index: number, item: ViewFile): string {
        return item.name;
    }

    onSelect(file: ViewFile): void {
        if (file.isSelected) {
            this.viewFileService.unsetSelected();
        } else {
            this.viewFileService.setSelected(file);
        }
    }

    onQueue(file: ViewFile) {
        this.viewFileService.queue(file).subscribe(data => {
            this._logger.info(data);
        });
    }

    onStop(file: ViewFile) {
        this.viewFileService.stop(file).subscribe(data => {
            this._logger.info(data);
        });
    }

    onExtract(file: ViewFile) {
        this.viewFileService.extract(file).subscribe(data => {
            this._logger.info(data);
        });
    }

    onDeleteLocal(file: ViewFile) {
        this.viewFileService.deleteLocal(file).subscribe(data => {
            this._logger.info(data);
        });
    }

    onDeleteRemote(file: ViewFile) {
        this.viewFileService.deleteRemote(file).subscribe(data => {
            this._logger.info(data);
        });
    }

    onValidate(file: ViewFile) {
        this.viewFileService.validate(file).subscribe(data => {
            this._logger.info(data);
        });
    }
}
