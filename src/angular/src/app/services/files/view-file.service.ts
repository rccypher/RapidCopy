import {Injectable} from "@angular/core";
import {Observable, forkJoin, of} from "rxjs";
import {BehaviorSubject} from "rxjs";

import * as Immutable from "immutable";

import {LoggerService} from "../utils/logger.service";
import {ModelFile} from "./model-file";
import {ModelFileService} from "./model-file.service";
import {ViewFile} from "./view-file";
import {MOCK_MODEL_FILES} from "./mock-model-files";
import {StreamServiceRegistry} from "../base/stream-service.registry";
import {WebReaction} from "../utils/rest.service";


/**
 * Interface defining filtering criteria for view files
 */
export interface ViewFileFilterCriteria {
    meetsCriteria(viewFile: ViewFile): boolean;
}


/**
 * Interface for sorting view files
 */
export interface ViewFileComparator {
    // noinspection TsLint
    (a: ViewFile, b: ViewFile): number;
}


/**
 * ViewFileService class provides the store of view files.
 * It implements the observable service pattern to push updates
 * as they become available.
 *
 * The view model needs to be ordered and have fast lookup/update.
 * Unfortunately, there exists no immutable SortedMap structure.
 * This class stores the following data structures:
 *    1. files: List(ViewFile)
 *              ViewFiles sorted in the display order
 *    2. indices: Map(name, index)
 *                Maps name to its index in sortedList
 * The runtime complexity of operations is:
 *    1. Update w/o state change:
 *          O(1) to find index and update the sorted list
 *    2. Updates w/ state change:
 *          O(1) to find index and update the sorted list
 *          O(n log n) to sort list (might be faster since
 *                     list is mostly sorted already??)
 *          O(n) to update indexMap
 *    3. Add:
 *          O(1) to add to list
 *          O(n log n) to sort list (might be faster since
 *                     list is mostly sorted already??)
 *          O(n) to update indexMap
 *    4. Remove:
 *          O(n) to remove from sorted list
 *          O(n) to update indexMap
 *
 * Filtering:
 *      This service also supports providing a filtered list of view files.
 *      The strategy of using pipes to filter at the component level is not
 *      recommended by Angular: https://angular.io/guide/pipes#appendix-no
 *      -filterpipe-or-orderbypipe
 *      Instead, we provide a separate filtered observer.
 *      Filtering is controlled via a single filter criteria. Advanced filters
 *      need to be built outside the service (see ViewFileFilterService)
 */
@Injectable()
export class ViewFileService {

    private readonly USE_MOCK_MODEL = false;

    private modelFileService: ModelFileService;

    private _files: Immutable.List<ViewFile> = Immutable.List([]);
    private _filesSubject: BehaviorSubject<Immutable.List<ViewFile>> = new BehaviorSubject(this._files);
    private _filteredFilesSubject: BehaviorSubject<Immutable.List<ViewFile>> = new BehaviorSubject(this._files);
    private _indices: Map<string, number> = new Map<string, number>();

    private _prevModelFiles: Immutable.Map<string, ModelFile> = Immutable.Map<string, ModelFile>();
    private _multiSelectedNames: Set<string> = new Set<string>();

    private _filterCriteria: ViewFileFilterCriteria = null;
    private _sortComparator: ViewFileComparator = null;

    constructor(private _logger: LoggerService,
                private _streamServiceRegistry: StreamServiceRegistry) {
        this.modelFileService = _streamServiceRegistry.modelFileService;
        const _viewFileService = this;

        if (!this.USE_MOCK_MODEL) {
            this.modelFileService.files.subscribe({
                next: modelFiles => {
                    let t0 = performance.now();
                    _viewFileService.buildViewFromModelFiles(modelFiles);
                    let t1 = performance.now();
                    this._logger.debug("ViewFile creation took", (t1 - t0).toFixed(0), "ms");
                }
            });
        } else {
            // For layout/style testing
            this.buildViewFromModelFiles(MOCK_MODEL_FILES);
        }
    }

    private buildViewFromModelFiles(modelFiles: Immutable.Map<string, ModelFile>) {
        this._logger.debug("Received next model files");

        // Diff the previous domain model with the current domain model, then apply
        // those changes to the view model
        // This is a roughly O(2N) operation on every update, so won't scale well
        // But should be fine for small models
        // A more scalable solution would be to subscribe to domain model updates
        let newViewFiles = this._files;

        const addedNames: string[] = [];
        const removedNames: string[] = [];
        const updatedNames: string[] = [];
        // Loop through old model to find deletions
        this._prevModelFiles.keySeq().forEach(
            name => {
                if (!modelFiles.has(name)) { removedNames.push(name); }
            }
        );
        // Loop through new model to find additions and updates
        modelFiles.keySeq().forEach(
            name => {
                if (!this._prevModelFiles.has(name)) {
                    addedNames.push(name);
                } else if (!Immutable.is(modelFiles.get(name), this._prevModelFiles.get(name))) {
                    updatedNames.push(name);
                }
            }
        );

        let reSort = false;
        let updateIndices = false;
        // Do the updates first before indices change (re-sort may be required)
        updatedNames.forEach(
            name => {
                const index = this._indices.get(name);
                const oldViewFile = newViewFiles.get(index);
                const newViewFile = ViewFileService.createViewFile(modelFiles.get(name), oldViewFile.isSelected);
                newViewFiles = newViewFiles.set(index, newViewFile);
                if (this._sortComparator != null && this._sortComparator(oldViewFile, newViewFile) !== 0) {
                    reSort = true;
                }
            }
        );
        // Do the adds (requires re-sort)
        addedNames.forEach(
            name => {
                reSort = true;
                const viewFile = ViewFileService.createViewFile(modelFiles.get(name));
                newViewFiles = newViewFiles.push(viewFile);
                this._indices.set(name, newViewFiles.size - 1);
            }
        );
        // Do the removes (no re-sort required)
        removedNames.forEach(
            name => {
                updateIndices = true;
                const index = newViewFiles.findIndex(value => value.name === name);
                newViewFiles = newViewFiles.remove(index);
                this._indices.delete(name);
            }
        );

        if (reSort && this._sortComparator != null) {
            this._logger.debug("Re-sorting view files");
            updateIndices = true;
            newViewFiles = newViewFiles.sort(this._sortComparator).toList();
        }
        if (updateIndices) {
            this._indices.clear();
            newViewFiles.forEach(
                (value, index) => this._indices.set(value.name, index)
            );
        }

        this._files = newViewFiles;
        this.pushViewFiles();
        this._prevModelFiles = modelFiles;
        this._logger.debug("New view model: %O", this._files.toJS());
    }

    get files(): Observable<Immutable.List<ViewFile>> {
        return this._filesSubject.asObservable();
    }

    get filteredFiles(): Observable<Immutable.List<ViewFile>> {
        return this._filteredFilesSubject.asObservable();
    }

    /**
     * Toggle multi-selection for a file (checkbox click)
     * @param {ViewFile} file
     */
    public toggleMultiSelected(file: ViewFile) {
        if (this._multiSelectedNames.has(file.name)) {
            this._multiSelectedNames.delete(file.name);
        } else {
            this._multiSelectedNames.add(file.name);
        }
        this.applyMultiSelection();
    }

    /**
     * Select a range of files (shift-click): selects all files between
     * the last multi-selected file and the clicked file.
     * @param {ViewFile} file
     */
    public rangeMultiSelect(file: ViewFile) {
        const fileList = this._files;
        if (this._multiSelectedNames.size === 0) {
            this._multiSelectedNames.add(file.name);
            this.applyMultiSelection();
            return;
        }
        // Find last selected index
        let lastIdx = -1;
        for (let i = 0; i < fileList.size; i++) {
            if (this._multiSelectedNames.has(fileList.get(i).name)) {
                lastIdx = i;
            }
        }
        const clickedIdx = fileList.findIndex(f => f.name === file.name);
        if (lastIdx < 0 || clickedIdx < 0) {
            this._multiSelectedNames.add(file.name);
        } else {
            const start = Math.min(lastIdx, clickedIdx);
            const end = Math.max(lastIdx, clickedIdx);
            for (let i = start; i <= end; i++) {
                this._multiSelectedNames.add(fileList.get(i).name);
            }
        }
        this.applyMultiSelection();
    }

    /**
     * Clear all multi-selections
     */
    public clearMultiSelected() {
        this._multiSelectedNames.clear();
        this.applyMultiSelection();
    }

    /**
     * Select all currently visible (filtered) files
     */
    public selectAllVisible() {
        // Get filtered files
        const filtered = this._filterCriteria != null
            ? this._files.filter(f => this._filterCriteria.meetsCriteria(f))
            : this._files;
        filtered.forEach(f => this._multiSelectedNames.add(f.name));
        this.applyMultiSelection();
    }

    /**
     * Get the set of currently multi-selected names
     */
    get multiSelectedNames(): Set<string> {
        return this._multiSelectedNames;
    }

    /**
     * Get currently multi-selected ViewFiles
     */
    get multiSelectedFiles(): ViewFile[] {
        return this._files.filter(f => this._multiSelectedNames.has(f.name)).toArray();
    }

    /**
     * Execute a bulk action on all multi-selected files that support it.
     * @param predicate - function that returns true if file supports the action
     * @param action    - action to execute on the file
     */
    public bulkAction(
        predicate: (f: ViewFile) => boolean,
        action: (f: ViewFile) => Observable<WebReaction>
    ): Observable<WebReaction[]> {
        const eligible = this.multiSelectedFiles.filter(predicate);
        if (eligible.length === 0) {
            return of([]);
        }
        return forkJoin(eligible.map(f => action(f)));
    }

    private applyMultiSelection() {
        let viewFiles = this._files;
        for (let i = 0; i < viewFiles.size; i++) {
            const f = viewFiles.get(i);
            const shouldBeMultiSelected = this._multiSelectedNames.has(f.name);
            if (f.isMultiSelected !== shouldBeMultiSelected) {
                viewFiles = viewFiles.set(i, new ViewFile(f.set("isMultiSelected", shouldBeMultiSelected)));
            }
        }
        this._files = viewFiles;
        this.pushViewFiles();
    }

    /**
     * Set a file to be in selected state
     * @param {ViewFile} file
     */
    public setSelected(file: ViewFile) {
        // Find the selected file, if any
        // Note: we can optimize this by storing an additional
        //       state that tracks the selected file
        //       but that would duplicate state and can introduce
        //       bugs, so we just search instead
        let viewFiles = this._files;
        const unSelectIndex = viewFiles.findIndex(value => value.isSelected);

        // Unset the previously selected file, if any
        if (unSelectIndex >= 0) {
            let unSelectViewFile = viewFiles.get(unSelectIndex);

            // Do nothing if file is already selected
            if (unSelectViewFile.name === file.name) { return; }

            unSelectViewFile = new ViewFile(unSelectViewFile.set("isSelected", false));
            viewFiles = viewFiles.set(unSelectIndex, unSelectViewFile);
        }

        // Set the new selected file
        if (this._indices.has(file.name)) {
            const index = this._indices.get(file.name);
            let viewFile = viewFiles.get(index);
            viewFile = new ViewFile(viewFile.set("isSelected", true));
            viewFiles = viewFiles.set(index, viewFile);
        } else {
            this._logger.error("Can't find file to select: " + file.name);
        }

        // Send update
        this._files = viewFiles;
        this.pushViewFiles();
    }

    /**
     * Un-select the currently selected file
     */
    public unsetSelected() {
        // Unset the previously selected file, if any
        let viewFiles = this._files;
        const unSelectIndex = viewFiles.findIndex(value => value.isSelected);

        // Unset the previously selected file, if any
        if (unSelectIndex >= 0) {
            let unSelectViewFile = viewFiles.get(unSelectIndex);

            unSelectViewFile = new ViewFile(unSelectViewFile.set("isSelected", false));
            viewFiles = viewFiles.set(unSelectIndex, unSelectViewFile);

            // Send update
            this._files = viewFiles;
            this.pushViewFiles();
        }
    }

    /**
     * Queue a file for download
     * @param {ViewFile} file
     * @returns {Observable<WebReaction>}
     */
    public queue(file: ViewFile): Observable<WebReaction> {
        this._logger.debug("Queue view file: " + file.name);
        return this.createAction(file, (f) => this.modelFileService.queue(f));
    }

    /**
     * Stop a file
     * @param {ViewFile} file
     * @returns {Observable<WebReaction>}
     */
    public stop(file: ViewFile): Observable<WebReaction> {
        this._logger.debug("Stop view file: " + file.name);
        return this.createAction(file, (f) => this.modelFileService.stop(f));
    }

    /**
     * Extract a file
     * @param {ViewFile} file
     * @returns {Observable<WebReaction>}
     */
    public extract(file: ViewFile): Observable<WebReaction> {
        this._logger.debug("Extract view file: " + file.name);
        return this.createAction(file, (f) => this.modelFileService.extract(f));
    }

    /**
     * Locally delete a file
     * @param {ViewFile} file
     * @returns {Observable<WebReaction>}
     */
    public deleteLocal(file: ViewFile): Observable<WebReaction> {
        this._logger.debug("Locally delete view file: " + file.name);
        return this.createAction(file, (f) => this.modelFileService.deleteLocal(f));
    }

    /**
     * Remotely delete a file
     * @param {ViewFile} file
     * @returns {Observable<WebReaction>}
     */
    public deleteRemote(file: ViewFile): Observable<WebReaction> {
        this._logger.debug("Remotely delete view file: " + file.name);
        return this.createAction(file, (f) => this.modelFileService.deleteRemote(f));
    }

    /**
     * Validate a file
     * @param {ViewFile} file
     * @returns {Observable<WebReaction>}
     */
    public validate(file: ViewFile): Observable<WebReaction> {
        this._logger.debug("Validate view file: " + file.name);
        return this.createAction(file, (f) => this.modelFileService.validate(f));
    }

    /**
     * Set a new filter criteria
     * @param {ViewFileFilterCriteria} criteria
     */
    public setFilterCriteria(criteria: ViewFileFilterCriteria) {
        this._filterCriteria = criteria;
        this.pushViewFiles();
    }

    /**
     * Sets a new comparator.
     * @param {ViewFileComparator} comparator
     */
    public setComparator(comparator: ViewFileComparator) {
        this._sortComparator = comparator;

        // Re-sort and regenerate index cache
        this._logger.debug("Re-sorting view files");
        let newViewFiles = this._files;
        if (this._sortComparator != null) {
            newViewFiles = newViewFiles.sort(this._sortComparator).toList();
        }
        this._files = newViewFiles;
        this._indices.clear();
        newViewFiles.forEach(
            (value, index) => this._indices.set(value.name, index)
        );

        this.pushViewFiles();
    }

    private static createViewFile(modelFile: ModelFile, isSelected: boolean = false): ViewFile {
        // Use zero for unknown sizes
        let localSize: number = modelFile.local_size;
        if (localSize == null) {
            localSize = 0;
        }
        let remoteSize: number = modelFile.remote_size;
        if (remoteSize == null) {
            remoteSize = 0;
        }
        let percentDownloaded: number = null;
        if (remoteSize > 0) {
            percentDownloaded = Math.round(100.0 * localSize / remoteSize);
        } else if (localSize > 0) {
            // Local-only file: no remote size known, treat as 100%
            percentDownloaded = 100;
        } else {
            // No local or remote data yet — show 0%
            percentDownloaded = 0;
        }

        // Translate the status
        let status = null;
        switch (modelFile.state) {
            case ModelFile.State.DEFAULT: {
                if (localSize > 0 && remoteSize > 0) {
                    status = ViewFile.Status.STOPPED;
                } else {
                    status = ViewFile.Status.DEFAULT;
                }
                break;
            }
            case ModelFile.State.QUEUED: {
                status = ViewFile.Status.QUEUED;
                break;
            }
            case ModelFile.State.DOWNLOADING: {
                status = ViewFile.Status.DOWNLOADING;
                break;
            }
            case ModelFile.State.DOWNLOADED: {
                status = ViewFile.Status.DOWNLOADED;
                break;
            }
            case ModelFile.State.DELETED: {
                status = ViewFile.Status.DELETED;
                break;
            }
            case ModelFile.State.EXTRACTING: {
                status = ViewFile.Status.EXTRACTING;
                break;
            }
            case ModelFile.State.EXTRACTED: {
                status = ViewFile.Status.EXTRACTED;
                break;
            }
            case ModelFile.State.VALIDATING: {
                status = ViewFile.Status.VALIDATING;
                break;
            }
            case ModelFile.State.VALIDATED: {
                status = ViewFile.Status.VALIDATED;
                break;
            }
            case ModelFile.State.CORRUPT: {
                status = ViewFile.Status.CORRUPT;
                break;
            }
        }

        const isQueueable: boolean = [ViewFile.Status.DEFAULT,
                                    ViewFile.Status.STOPPED,
                                    ViewFile.Status.DELETED,
                                    ViewFile.Status.CORRUPT].includes(status)
                                    && remoteSize > 0;
        const isStoppable: boolean = [ViewFile.Status.QUEUED,
                                    ViewFile.Status.DOWNLOADING].includes(status);
        const isExtractable: boolean = [ViewFile.Status.DEFAULT,
                                    ViewFile.Status.STOPPED,
                                    ViewFile.Status.DOWNLOADED,
                                    ViewFile.Status.EXTRACTED,
                                    ViewFile.Status.VALIDATED].includes(status)
                                    && localSize > 0;
        const isLocallyDeletable: boolean = [ViewFile.Status.DEFAULT,
                                    ViewFile.Status.STOPPED,
                                    ViewFile.Status.DOWNLOADED,
                                    ViewFile.Status.EXTRACTED,
                                    ViewFile.Status.VALIDATED,
                                    ViewFile.Status.CORRUPT].includes(status)
                                    && localSize > 0;
        const isRemotelyDeletable: boolean = [ViewFile.Status.DEFAULT,
                                    ViewFile.Status.STOPPED,
                                    ViewFile.Status.DOWNLOADED,
                                    ViewFile.Status.EXTRACTED,
                                    ViewFile.Status.DELETED,
                                    ViewFile.Status.VALIDATED,
                                    ViewFile.Status.CORRUPT].includes(status)
                                    && remoteSize > 0;
        const isValidatable: boolean = [ViewFile.Status.DEFAULT,
                                    ViewFile.Status.STOPPED,
                                    ViewFile.Status.DOWNLOADED,
                                    ViewFile.Status.EXTRACTED,
                                    ViewFile.Status.VALIDATED,
                                    ViewFile.Status.CORRUPT].includes(status)
                                    && localSize > 0 && remoteSize > 0;

        return new ViewFile({
            name: modelFile.name,
            isDir: modelFile.is_dir,
            localSize: localSize,
            remoteSize: remoteSize,
            percentDownloaded: percentDownloaded,
            status: status,
            downloadingSpeed: modelFile.downloading_speed,
            eta: modelFile.eta,
            fullPath: modelFile.full_path,
            isArchive: modelFile.is_extractable,
            isSelected: isSelected,
            isMultiSelected: false,
            isQueueable: isQueueable,
            isStoppable: isStoppable,
            isExtractable: isExtractable,
            isLocallyDeletable: isLocallyDeletable,
            isRemotelyDeletable: isRemotelyDeletable,
            isValidatable: isValidatable,
            localCreatedTimestamp: modelFile.local_created_timestamp,
            localModifiedTimestamp: modelFile.local_modified_timestamp,
            remoteCreatedTimestamp: modelFile.remote_created_timestamp,
            remoteModifiedTimestamp: modelFile.remote_modified_timestamp,
            pathPairId: modelFile.path_pair_id,
            pathPairName: modelFile.path_pair_name,
            validationProgress: modelFile.validation_progress,
            validationError: modelFile.validation_error,
            corruptChunks: modelFile.corrupt_chunks
        });
    }

    /**
     * Helper method to execute an action on ModelFileService and generate a ViewFileReaction
     * @param {ViewFile} file
     * @param {Observable<WebReaction>} action
     * @returns {Observable<WebReaction>}
     */
    private createAction(file: ViewFile,
                         action: (file: ModelFile) => Observable<WebReaction>)
            : Observable<WebReaction> {
        return Observable.create(observer => {
            if (!this._prevModelFiles.has(file.name)) {
                // File not found, exit early
                this._logger.error("File to queue not found: " + file.name);
                observer.next(new WebReaction(false, null, `File '${file.name}' not found`));
            } else {
                const modelFile = this._prevModelFiles.get(file.name);
                action(modelFile).subscribe(reaction => {
                    this._logger.debug("Received model reaction: %O", reaction);
                    observer.next(reaction);
                });
            }
        });
    }

    private pushViewFiles() {
        // Unfiltered files
        this._filesSubject.next(this._files);

        // Filtered files
        let filteredFiles = this._files;
        if (this._filterCriteria != null) {
            filteredFiles = Immutable.List<ViewFile>(
                this._files.filter(f => this._filterCriteria.meetsCriteria(f))
            );
        }
        this._filteredFilesSubject.next(filteredFiles);
    }
}
