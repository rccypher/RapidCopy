import {Component, OnInit, OnDestroy} from "@angular/core";
import {CommonModule} from "@angular/common";
import {FormsModule} from "@angular/forms";
import {Subject} from "rxjs";
import {takeUntil} from "rxjs/operators";

import {NetworkMountService, NetworkMount, NetworkMountResult} from "../../services/settings/network-mount.service";
import {NotificationService} from "../../services/utils/notification.service";
import {Notification} from "../../services/utils/notification";

type MountType = "nfs" | "cifs" | "local";
type MountStatus = "mounted" | "unmounted" | "error" | "unknown";

@Component({
    selector: "app-network-mounts",
    standalone: true,
    imports: [CommonModule, FormsModule],
    templateUrl: "./network-mounts.component.html",
    styleUrls: ["./network-mounts.component.scss"]
})
export class NetworkMountsComponent implements OnInit, OnDestroy {
    mounts: NetworkMount[] = [];
    isEditing = false;
    editingMount: NetworkMount | null = null;
    isCreating = false;
    isLoading = false;
    testingId: string | null = null;
    mountingId: string | null = null;

    // Form fields for new/edit
    formName = "";
    formMountType: MountType = "cifs";
    formServer = "";
    formSharePath = "";
    formUsername = "";
    formPassword = "";
    formDomain = "";
    formMountOptions = "";
    formEnabled = true;

    private destroy$ = new Subject<void>();

    constructor(
        private networkMountService: NetworkMountService,
        private notificationService: NotificationService
    ) {}

    ngOnInit(): void {
        this.networkMountService.mounts$
            .pipe(takeUntil(this.destroy$))
            .subscribe(mounts => {
                this.mounts = mounts;
            });
    }

    ngOnDestroy(): void {
        this.destroy$.next();
        this.destroy$.complete();
    }

    // Start creating a new mount
    startCreate(): void {
        this.isCreating = true;
        this.isEditing = false;
        this.editingMount = null;
        this.clearForm();
    }

    // Start editing an existing mount
    startEdit(mount: NetworkMount): void {
        this.isEditing = true;
        this.isCreating = false;
        this.editingMount = mount;
        this.formName = mount.name;
        this.formMountType = mount.mount_type;
        this.formServer = mount.server;
        this.formSharePath = mount.share_path;
        this.formUsername = mount.username || "";
        this.formPassword = ""; // Don't show existing password
        this.formDomain = mount.domain || "";
        this.formMountOptions = mount.mount_options || "";
        this.formEnabled = mount.enabled;
    }

    // Cancel editing/creating
    cancel(): void {
        this.isEditing = false;
        this.isCreating = false;
        this.editingMount = null;
        this.clearForm();
    }

    // Save (create or update)
    save(): void {
        if (!this.formName) {
            this.showError("Name is required");
            return;
        }
        if (!this.formServer && this.formMountType !== "local") {
            this.showError("Server is required for network mounts");
            return;
        }
        if (!this.formSharePath) {
            this.showError("Share path is required");
            return;
        }

        if (this.isCreating) {
            this.networkMountService.create({
                name: this.formName,
                mount_type: this.formMountType,
                server: this.formServer,
                share_path: this.formSharePath,
                username: this.formUsername || null,
                password: this.formPassword || null,
                domain: this.formDomain || null,
                mount_options: this.formMountOptions,
                enabled: this.formEnabled
            }).subscribe({
                next: (result: NetworkMountResult) => {
                    this.showSuccess("Network mount created");
                    this.showWarnings(result.warnings);
                    this.cancel();
                },
                error: (err) => this.showError(`Failed to create: ${err.message}`)
            });
        } else if (this.isEditing && this.editingMount) {
            const updateData: Partial<NetworkMount> & {id: string} = {
                id: this.editingMount.id,
                name: this.formName,
                mount_type: this.formMountType,
                server: this.formServer,
                share_path: this.formSharePath,
                username: this.formUsername || null,
                domain: this.formDomain || null,
                mount_options: this.formMountOptions,
                enabled: this.formEnabled
            };
            
            // Only include password if it was changed
            if (this.formPassword) {
                updateData.password = this.formPassword;
            }
            
            this.networkMountService.update(updateData).subscribe({
                next: (result: NetworkMountResult) => {
                    this.showSuccess("Network mount updated");
                    this.showWarnings(result.warnings);
                    this.cancel();
                },
                error: (err) => this.showError(`Failed to update: ${err.message}`)
            });
        }
    }

    // Delete a mount
    delete(mount: NetworkMount): void {
        if (confirm(`Are you sure you want to delete "${mount.name}"?`)) {
            this.networkMountService.delete(mount.id).subscribe({
                next: () => {
                    this.showSuccess("Network mount deleted");
                    if (this.editingMount?.id === mount.id) {
                        this.cancel();
                    }
                },
                error: (err) => this.showError(`Failed to delete: ${err.message}`)
            });
        }
    }

    // Toggle enabled status
    toggleEnabled(mount: NetworkMount): void {
        this.networkMountService.update({
            id: mount.id,
            enabled: !mount.enabled
        }).subscribe({
            error: (err) => this.showError(`Failed to toggle: ${err.message}`)
        });
    }

    // Mount action
    mountShare(mount: NetworkMount): void {
        this.mountingId = mount.id;
        this.networkMountService.mount(mount.id).subscribe({
            next: (message) => {
                this.showSuccess(message);
                this.mountingId = null;
            },
            error: (err) => {
                this.showError(`Failed to mount: ${err.message}`);
                this.mountingId = null;
            }
        });
    }

    // Unmount action
    unmountShare(mount: NetworkMount): void {
        this.mountingId = mount.id;
        this.networkMountService.unmount(mount.id).subscribe({
            next: (message) => {
                this.showSuccess(message);
                this.mountingId = null;
            },
            error: (err) => {
                this.showError(`Failed to unmount: ${err.message}`);
                this.mountingId = null;
            }
        });
    }

    // Force unmount
    forceUnmount(mount: NetworkMount): void {
        if (confirm("Force unmount may cause data loss if files are being written. Continue?")) {
            this.mountingId = mount.id;
            this.networkMountService.unmount(mount.id, true).subscribe({
                next: (message) => {
                    this.showSuccess(message);
                    this.mountingId = null;
                },
                error: (err) => {
                    this.showError(`Failed to force unmount: ${err.message}`);
                    this.mountingId = null;
                }
            });
        }
    }

    // Test connection
    testConnection(mount: NetworkMount): void {
        this.testingId = mount.id;
        this.networkMountService.testConnection(mount.id).subscribe({
            next: (result) => {
                if (result.connected) {
                    this.showSuccess(`Connection successful: ${result.message}`);
                } else {
                    this.showError(`Connection failed: ${result.message}`);
                }
                this.testingId = null;
            },
            error: (err) => {
                this.showError(`Test failed: ${err.message}`);
                this.testingId = null;
            }
        });
    }

    // Helper to get mount type display name
    getMountTypeLabel(type: MountType): string {
        switch (type) {
            case "cifs": return "SMB/CIFS";
            case "nfs": return "NFS";
            case "local": return "Local";
            default: return type;
        }
    }

    // Helper to get status badge class
    getStatusClass(status: MountStatus): string {
        switch (status) {
            case "mounted": return "status-mounted";
            case "unmounted": return "status-unmounted";
            case "error": return "status-error";
            default: return "status-unknown";
        }
    }

    // Helper to get status display name
    getStatusLabel(status: MountStatus): string {
        switch (status) {
            case "mounted": return "Mounted";
            case "unmounted": return "Unmounted";
            case "error": return "Error";
            default: return "Unknown";
        }
    }

    private clearForm(): void {
        this.formName = "";
        this.formMountType = "cifs";
        this.formServer = "";
        this.formSharePath = "";
        this.formUsername = "";
        this.formPassword = "";
        this.formDomain = "";
        this.formMountOptions = "";
        this.formEnabled = true;
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

    private showWarnings(warnings: string[]): void {
        for (const warning of warnings) {
            this.notificationService.show(new Notification({
                level: Notification.Level.WARNING,
                text: warning,
                dismissible: true
            }));
        }
    }
}
