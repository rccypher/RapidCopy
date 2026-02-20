import {Component, ChangeDetectionStrategy, ChangeDetectorRef, OnInit, OnDestroy} from "@angular/core";
import {Observable, Subscription} from "rxjs";

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

export class FileListComponent implements OnInit, OnDestroy {
    public files: Observable<List<ViewFile>>;
    public identify = FileListComponent.identify;
    public options: Observable<ViewFileOptions>;

    // Column header sort state
    public activeSortColumn: string = null;
    public sortAscending = true;

    // Multi-select toolbar state (derived from service, updated on file changes)
    public multiSelectCount = 0;
    public canQueueAny = false;
    public canStopAny = false;
    public canExtractAny = false;
    public canDeleteLocalAny = false;
    public canDeleteRemoteAny = false;
    public canValidateAny = false;
    public allVisibleSelected = false;

    // Bulk action in-progress flags
    public bulkQueuing = false;
    public bulkStopping = false;
    public bulkExtracting = false;
    public bulkDeletingLocal = false;
    public bulkDeletingRemote = false;
    public bulkValidating = false;

    private _filesSubscription: Subscription;

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

    ngOnInit() {
        // Subscribe to file updates to keep toolbar state current
        this._filesSubscription = this.viewFileService.filteredFiles.subscribe(files => {
            const selected = files.filter(f => f.isMultiSelected).toArray();
            this.multiSelectCount = selected.length;
            this.canQueueAny = selected.some(f => f.isQueueable);
            this.canStopAny = selected.some(f => f.isStoppable);
            this.canExtractAny = selected.some(f => f.isExtractable && f.isArchive);
            this.canDeleteLocalAny = selected.some(f => f.isLocallyDeletable);
            this.canDeleteRemoteAny = selected.some(f => f.isRemotelyDeletable);
            this.canValidateAny = selected.some(f => f.isValidatable);
            // All visible selected?
            this.allVisibleSelected = files.size > 0 && files.every(f => f.isMultiSelected);
            this._changeDetector.markForCheck();
        });
    }

    ngOnDestroy() {
        if (this._filesSubscription) {
            this._filesSubscription.unsubscribe();
        }
    }

    onHeaderSort(column: string): void {
        const mapping = FileListComponent.COLUMN_SORT_MAP[column];
        if (!mapping) return;

        if (this.activeSortColumn === column) {
            if (mapping.asc !== mapping.desc) {
                this.sortAscending = !this.sortAscending;
            }
        } else {
            this.activeSortColumn = column;
            this.sortAscending = true;
        }

        const sortMethod = this.sortAscending ? mapping.asc : mapping.desc;
        this.viewFileOptionsService.setSortMethod(sortMethod);
        this._changeDetector.markForCheck();
    }

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

    // --- Checkbox / multi-select ---

    onCheckbox(event: {file: ViewFile, shiftKey: boolean}) {
        if (event.shiftKey) {
            this.viewFileService.rangeMultiSelect(event.file);
        } else {
            this.viewFileService.toggleMultiSelected(event.file);
        }
    }

    onSelectAllToggle(event: Event) {
        event.stopPropagation();
        if (this.allVisibleSelected) {
            this.viewFileService.clearMultiSelected();
        } else {
            this.viewFileService.selectAllVisible();
        }
    }

    onClearSelection() {
        this.viewFileService.clearMultiSelected();
    }

    // --- Single-file actions (pass-through from FileComponent) ---

    onQueue(file: ViewFile) {
        this.viewFileService.queue(file).subscribe(data => this._logger.info(data));
    }

    onStop(file: ViewFile) {
        this.viewFileService.stop(file).subscribe(data => this._logger.info(data));
    }

    onExtract(file: ViewFile) {
        this.viewFileService.extract(file).subscribe(data => this._logger.info(data));
    }

    onDeleteLocal(file: ViewFile) {
        this.viewFileService.deleteLocal(file).subscribe(data => this._logger.info(data));
    }

    onDeleteRemote(file: ViewFile) {
        this.viewFileService.deleteRemote(file).subscribe(data => this._logger.info(data));
    }

    onValidate(file: ViewFile) {
        this.viewFileService.validate(file).subscribe(data => this._logger.info(data));
    }

    // --- Bulk actions ---

    onBulkQueue() {
        if (!this.canQueueAny || this.bulkQueuing) return;
        this.bulkQueuing = true;
        this._changeDetector.markForCheck();
        this.viewFileService.bulkAction(
            f => f.isQueueable,
            f => this.viewFileService.queue(f)
        ).subscribe({
            next: () => { this.bulkQueuing = false; this._changeDetector.markForCheck(); },
            error: () => { this.bulkQueuing = false; this._changeDetector.markForCheck(); }
        });
    }

    onBulkStop() {
        if (!this.canStopAny || this.bulkStopping) return;
        this.bulkStopping = true;
        this._changeDetector.markForCheck();
        this.viewFileService.bulkAction(
            f => f.isStoppable,
            f => this.viewFileService.stop(f)
        ).subscribe({
            next: () => { this.bulkStopping = false; this._changeDetector.markForCheck(); },
            error: () => { this.bulkStopping = false; this._changeDetector.markForCheck(); }
        });
    }

    onBulkExtract() {
        if (!this.canExtractAny || this.bulkExtracting) return;
        this.bulkExtracting = true;
        this._changeDetector.markForCheck();
        this.viewFileService.bulkAction(
            f => f.isExtractable && f.isArchive,
            f => this.viewFileService.extract(f)
        ).subscribe({
            next: () => { this.bulkExtracting = false; this._changeDetector.markForCheck(); },
            error: () => { this.bulkExtracting = false; this._changeDetector.markForCheck(); }
        });
    }

    onBulkDeleteLocal() {
        if (!this.canDeleteLocalAny || this.bulkDeletingLocal) return;
        const count = this.viewFileService.multiSelectedFiles.filter(f => f.isLocallyDeletable).length;
        if (!confirm(`Delete Local\n\nDelete the local copy of ${count} file(s)? This cannot be undone.`)) return;
        this.bulkDeletingLocal = true;
        this._changeDetector.markForCheck();
        this.viewFileService.bulkAction(
            f => f.isLocallyDeletable,
            f => this.viewFileService.deleteLocal(f)
        ).subscribe({
            next: () => { this.bulkDeletingLocal = false; this._changeDetector.markForCheck(); },
            error: () => { this.bulkDeletingLocal = false; this._changeDetector.markForCheck(); }
        });
    }

    onBulkDeleteRemote() {
        if (!this.canDeleteRemoteAny || this.bulkDeletingRemote) return;
        const count = this.viewFileService.multiSelectedFiles.filter(f => f.isRemotelyDeletable).length;
        if (!confirm(`Delete Remote\n\nDelete ${count} file(s) from the remote server? This cannot be undone.`)) return;
        this.bulkDeletingRemote = true;
        this._changeDetector.markForCheck();
        this.viewFileService.bulkAction(
            f => f.isRemotelyDeletable,
            f => this.viewFileService.deleteRemote(f)
        ).subscribe({
            next: () => { this.bulkDeletingRemote = false; this._changeDetector.markForCheck(); },
            error: () => { this.bulkDeletingRemote = false; this._changeDetector.markForCheck(); }
        });
    }

    onBulkValidate() {
        if (!this.canValidateAny || this.bulkValidating) return;
        this.bulkValidating = true;
        this._changeDetector.markForCheck();
        this.viewFileService.bulkAction(
            f => f.isValidatable,
            f => this.viewFileService.validate(f)
        ).subscribe({
            next: () => { this.bulkValidating = false; this._changeDetector.markForCheck(); },
            error: () => { this.bulkValidating = false; this._changeDetector.markForCheck(); }
        });
    }
}
