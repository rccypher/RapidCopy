import {Component, OnInit, OnDestroy} from "@angular/core";
import {CommonModule} from "@angular/common";
import {FormsModule} from "@angular/forms";
import {Subject} from "rxjs";
import {takeUntil} from "rxjs/operators";

import {PathPairService, PathPair} from "../../services/settings/path-pair.service";
import {NotificationService} from "../../services/utils/notification.service";
import {Notification} from "../../services/utils/notification";

@Component({
    selector: "app-path-pairs",
    standalone: true,
    imports: [CommonModule, FormsModule],
    templateUrl: "./path-pairs.component.html",
    styleUrls: ["./path-pairs.component.scss"]
})
export class PathPairsComponent implements OnInit, OnDestroy {
    pathPairs: PathPair[] = [];
    isEditing = false;
    editingPair: PathPair | null = null;
    isCreating = false;
    
    // Form fields for new/edit
    formName = "";
    formRemotePath = "";
    formLocalPath = "";
    formEnabled = true;
    formAutoQueue = true;

    private destroy$ = new Subject<void>();

    constructor(
        private pathPairService: PathPairService,
        private notificationService: NotificationService
    ) {}

    ngOnInit(): void {
        this.pathPairService.pathPairs$
            .pipe(takeUntil(this.destroy$))
            .subscribe(pairs => {
                this.pathPairs = pairs;
            });
    }

    ngOnDestroy(): void {
        this.destroy$.next();
        this.destroy$.complete();
    }

    // Start creating a new path pair
    startCreate(): void {
        this.isCreating = true;
        this.isEditing = false;
        this.editingPair = null;
        this.clearForm();
    }

    // Start editing an existing path pair
    startEdit(pair: PathPair): void {
        this.isEditing = true;
        this.isCreating = false;
        this.editingPair = pair;
        this.formName = pair.name;
        this.formRemotePath = pair.remote_path;
        this.formLocalPath = pair.local_path;
        this.formEnabled = pair.enabled;
        this.formAutoQueue = pair.auto_queue;
    }

    // Cancel editing/creating
    cancel(): void {
        this.isEditing = false;
        this.isCreating = false;
        this.editingPair = null;
        this.clearForm();
    }

    // Save (create or update)
    save(): void {
        if (!this.formRemotePath || !this.formLocalPath) {
            this.showError("Remote path and local path are required");
            return;
        }

        if (this.isCreating) {
            this.pathPairService.create({
                name: this.formName || this.getDefaultName(this.formRemotePath),
                remote_path: this.formRemotePath,
                local_path: this.formLocalPath,
                enabled: this.formEnabled,
                auto_queue: this.formAutoQueue
            }).subscribe({
                next: () => {
                    this.showSuccess("Path pair created");
                    this.cancel();
                },
                error: (err) => this.showError(`Failed to create: ${err.message}`)
            });
        } else if (this.isEditing && this.editingPair) {
            this.pathPairService.update({
                id: this.editingPair.id,
                name: this.formName,
                remote_path: this.formRemotePath,
                local_path: this.formLocalPath,
                enabled: this.formEnabled,
                auto_queue: this.formAutoQueue
            }).subscribe({
                next: () => {
                    this.showSuccess("Path pair updated");
                    this.cancel();
                },
                error: (err) => this.showError(`Failed to update: ${err.message}`)
            });
        }
    }

    // Delete a path pair
    delete(pair: PathPair): void {
        if (confirm(`Are you sure you want to delete "${pair.name}"?`)) {
            this.pathPairService.delete(pair.id).subscribe({
                next: () => {
                    this.showSuccess("Path pair deleted");
                    if (this.editingPair?.id === pair.id) {
                        this.cancel();
                    }
                },
                error: (err) => this.showError(`Failed to delete: ${err.message}`)
            });
        }
    }

    // Toggle enabled status
    toggleEnabled(pair: PathPair): void {
        this.pathPairService.update({
            ...pair,
            enabled: !pair.enabled
        }).subscribe({
            error: (err) => this.showError(`Failed to toggle: ${err.message}`)
        });
    }

    // Move a path pair up in the list
    moveUp(index: number): void {
        if (index <= 0) return;
        const ids = this.pathPairs.map(p => p.id);
        [ids[index - 1], ids[index]] = [ids[index], ids[index - 1]];
        this.pathPairService.reorder(ids).subscribe({
            error: (err) => this.showError(`Failed to reorder: ${err.message}`)
        });
    }

    // Move a path pair down in the list
    moveDown(index: number): void {
        if (index >= this.pathPairs.length - 1) return;
        const ids = this.pathPairs.map(p => p.id);
        [ids[index], ids[index + 1]] = [ids[index + 1], ids[index]];
        this.pathPairService.reorder(ids).subscribe({
            error: (err) => this.showError(`Failed to reorder: ${err.message}`)
        });
    }

    private clearForm(): void {
        this.formName = "";
        this.formRemotePath = "";
        this.formLocalPath = "";
        this.formEnabled = true;
        this.formAutoQueue = true;
    }

    private getDefaultName(remotePath: string): string {
        const parts = remotePath.replace(/\/+$/, "").split("/");
        return parts[parts.length - 1] || "Default";
    }

    private showSuccess(message: string): void {
        this.notificationService.show(new Notification({
            level: Notification.Level.SUCCESS,
            text: message,
            dismissible: true
        }));
    }

    private showError(message: string): void {
        this.notificationService.show(new Notification({
            level: Notification.Level.DANGER,
            text: message,
            dismissible: true
        }));
    }
}
