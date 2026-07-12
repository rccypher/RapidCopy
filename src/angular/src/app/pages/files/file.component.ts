import {
    Component, Input, Output, ChangeDetectionStrategy,
    EventEmitter, OnChanges, SimpleChanges, ViewChild
} from "@angular/core";

import {NgbModal} from "@ng-bootstrap/ng-bootstrap";
import {ConfirmModalComponent} from "../main/confirm-modal.component";

import {ViewFile} from "../../services/files/view-file";
import {Localization} from "../../common/localization";
import {ViewFileOptions} from "../../services/files/view-file-options";

@Component({
    selector: "app-file",
    providers: [],
    templateUrl: "./file.component.html",
    styleUrls: ["./file.component.scss"],
    changeDetection: ChangeDetectionStrategy.OnPush
})

export class FileComponent implements OnChanges {
    // Make ViewFile optionType accessible from template
    ViewFile = ViewFile;

    // Make FileAction accessible from template
    FileAction = FileAction;

    // Expose min function for template
    min = Math.min;

    // Entire div element
    @ViewChild("fileElement") fileElement: any;

    @Input() file: ViewFile;
    @Input() options: ViewFileOptions;

    @Output() checkboxEvent = new EventEmitter<{file: ViewFile, shiftKey: boolean}>();
    @Output() queueEvent = new EventEmitter<ViewFile>();
    @Output() stopEvent = new EventEmitter<ViewFile>();
    @Output() extractEvent = new EventEmitter<ViewFile>();
    @Output() deleteLocalEvent = new EventEmitter<ViewFile>();
    @Output() deleteRemoteEvent = new EventEmitter<ViewFile>();
    @Output() validateEvent = new EventEmitter<ViewFile>();
    @Output() prioritizeEvent = new EventEmitter<ViewFile>();

    // Indicates an active action on-going
    activeAction: FileAction = null;
    private _actionTimeout: any = null;

    constructor(private modalService: NgbModal) {}

    ngOnChanges(changes: SimpleChanges): void {
        // Check for status changes
        const oldFile: ViewFile = changes.file.previousValue;
        const newFile: ViewFile = changes.file.currentValue;
        if (oldFile != null && newFile != null && oldFile.status !== newFile.status) {
            // Reset any active action
            this.clearActionTimeout();
            this.activeAction = null;

            // Scroll into view if this file is selected and not already in viewport
            if (newFile.isSelected && !FileComponent.isElementInViewport(this.fileElement.nativeElement)) {
                this.fileElement.nativeElement.scrollIntoView();
            }
        }
    }

    showDeleteConfirmation(title: string, message: string, callback: () => void) {
        const ref = this.modalService.open(ConfirmModalComponent, {centered: true});
        ref.componentInstance.title = title;
        // messages may contain simple HTML (e.g. <b>name</b>); the modal renders text, so strip tags
        ref.componentInstance.message = message.replace(/<[^>]+>/g, "");
        ref.componentInstance.confirmText = "Delete";
        ref.componentInstance.danger = true;
        ref.result.then(
            (confirmed) => { if (confirmed) { callback(); } },
            () => { /* dismissed / cancelled */ }
        );
    }

    isQueueable() {
        return this.activeAction == null && this.file.isQueueable;
    }

    isStoppable() {
        return this.activeAction == null && this.file.isStoppable;
    }

    isExtractable() {
        return this.activeAction == null && this.file.isExtractable && this.file.isArchive;
    }

    isLocallyDeletable() {
        return this.activeAction == null && this.file.isLocallyDeletable;
    }

    isRemotelyDeletable() {
        return this.activeAction == null && this.file.isRemotelyDeletable;
    }

    isValidatable() {
        return this.activeAction == null && this.file.isValidatable;
    }

    isPrioritizable() {
        return this.activeAction == null && this.file.isPrioritizable;
    }

    onCheckboxClick(event: MouseEvent) {
        event.stopPropagation();
        this.checkboxEvent.emit({file: this.file, shiftKey: event.shiftKey});
    }

    // Set the in-flight action and start a safety timer. The spinner is normally
    // cleared by ngOnChanges when the file's status changes; but some actions don't
    // change status (e.g. re-queue/re-validate), which would leave the spinner stuck
    // — so auto-clear after a few seconds as a fallback.
    private startAction(action: FileAction): void {
        this.activeAction = action;
        this.clearActionTimeout();
        this._actionTimeout = setTimeout(() => {
            this.activeAction = null;
            this._actionTimeout = null;
        }, 5000);
    }

    private clearActionTimeout(): void {
        if (this._actionTimeout != null) {
            clearTimeout(this._actionTimeout);
            this._actionTimeout = null;
        }
    }

    onQueue(file: ViewFile) {
        this.startAction(FileAction.QUEUE);
        // Pass to parent component
        this.queueEvent.emit(file);
    }

    onStop(file: ViewFile) {
        this.startAction(FileAction.STOP);
        // Pass to parent component
        this.stopEvent.emit(file);
    }

    onExtract(file: ViewFile) {
        this.startAction(FileAction.EXTRACT);
        // Pass to parent component
        this.extractEvent.emit(file);
    }

    onDeleteLocal(file: ViewFile) {
        this.showDeleteConfirmation(
            Localization.Modal.DELETE_LOCAL_TITLE,
            Localization.Modal.DELETE_LOCAL_MESSAGE(file.name),
            () => {
                this.startAction(FileAction.DELETE_LOCAL);
                // Pass to parent component
                this.deleteLocalEvent.emit(file);
            }
        );
    }

    onDeleteRemote(file: ViewFile) {
        this.showDeleteConfirmation(
            Localization.Modal.DELETE_REMOTE_TITLE,
            Localization.Modal.DELETE_REMOTE_MESSAGE(file.name),
            () => {
                this.startAction(FileAction.DELETE_REMOTE);
                // Pass to parent component
                this.deleteRemoteEvent.emit(file);
            }
        );
    }

    onValidate(file: ViewFile) {
        this.startAction(FileAction.VALIDATE);
        // Pass to parent component
        this.validateEvent.emit(file);
    }

    onPrioritize(file: ViewFile) {
        this.startAction(FileAction.PRIORITIZE);
        // Pass to parent component
        this.prioritizeEvent.emit(file);
    }

    // Source: https://stackoverflow.com/a/7557433
    private static isElementInViewport (el) {
        const rect = el.getBoundingClientRect();
        return (
            rect.top >= 0 &&
            rect.left >= 0 &&
            rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) && /*or $(window).height() */
            rect.right <= (window.innerWidth || document.documentElement.clientWidth) /*or $(window).width() */
        );
    }
}

export enum FileAction {
    QUEUE,
    STOP,
    EXTRACT,
    DELETE_LOCAL,
    DELETE_REMOTE,
    VALIDATE,
    PRIORITIZE
}
