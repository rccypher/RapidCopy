import { Component, OnInit, OnDestroy } from "@angular/core";
import { Subscription } from "rxjs";

import { UpdateService, UpdateStatus } from "../../services/utils/update.service";

declare function require(moduleName: string): any;
const { version: appVersion } = require('../../../../package.json');

@Component({
    selector: "app-about-page",
    templateUrl: "./about-page.component.html",
    styleUrls: ["./about-page.component.scss"],
    providers: [],
})
export class AboutPageComponent implements OnInit, OnDestroy {
    public version: string;
    
    // Update feature
    public updateAvailable = false;
    public updateStatus: UpdateStatus | null = null;
    public isUpdating = false;
    public updateError: string | null = null;
    
    private _subscriptions: Subscription[] = [];

    constructor(private _updateService: UpdateService) {
        this.version = appVersion;
    }

    ngOnInit(): void {
        // Subscribe to update availability
        this._subscriptions.push(
            this._updateService.updateAvailable$.subscribe(available => {
                this.updateAvailable = available;
            })
        );

        // Subscribe to update status
        this._subscriptions.push(
            this._updateService.status$.subscribe(status => {
                this.updateStatus = status;
                this.isUpdating = status?.status === "updating";
            })
        );

        // Check health on init
        this._updateService.checkHealth().subscribe();
    }

    ngOnDestroy(): void {
        this._subscriptions.forEach(sub => sub.unsubscribe());
        this._updateService.stopPolling();
    }

    /**
     * Trigger an update
     */
    triggerUpdate(): void {
        if (this.isUpdating) {
            return;
        }

        this.updateError = null;
        this._updateService.triggerUpdate().subscribe({
            error: err => {
                this.updateError = err.message;
            }
        });
    }

    /**
     * Get a user-friendly status message
     */
    getStatusMessage(): string {
        if (!this.updateStatus) {
            return "";
        }

        switch (this.updateStatus.status) {
            case "idle":
                return "Ready to update";
            case "updating":
                return "Update in progress...";
            case "success":
                return "Update completed successfully";
            case "failed":
                return `Update failed: ${this.updateStatus.message}`;
            default:
                return "";
        }
    }

    /**
     * Check if we can show the update button
     */
    canUpdate(): boolean {
        return this.updateAvailable && !this.isUpdating;
    }
}
