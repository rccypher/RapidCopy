import { Injectable } from "@angular/core";
import { HttpClient, HttpErrorResponse } from "@angular/common/http";
import { Observable, BehaviorSubject, timer } from "rxjs";
import { map, catchError, switchMap, takeWhile, finalize } from "rxjs/operators";

import { LoggerService } from "./logger.service";
import { NotificationService } from "./notification.service";
import { Notification } from "./notification";

/**
 * Update status returned by the update server
 */
export interface UpdateStatus {
    status: "idle" | "updating" | "success" | "failed";
    message: string;
    started_at: string | null;
    completed_at: string | null;
    output?: string;
}

/**
 * Health check response
 */
export interface UpdateHealthCheck {
    available: boolean;
    configured: boolean;
    server_status?: string;
    error?: string;
}

/**
 * UpdateService handles communication with the backend update proxy
 * which forwards requests to the host sidecar update server.
 */
@Injectable()
export class UpdateService {
    private readonly BASE_URL = "/server/update";
    
    // Observable status that components can subscribe to
    private _status$ = new BehaviorSubject<UpdateStatus | null>(null);
    private _isPolling = false;
    private _updateAvailable$ = new BehaviorSubject<boolean>(false);

    constructor(
        private _http: HttpClient,
        private _logger: LoggerService,
        private _notifService: NotificationService
    ) {
        // Check if update server is available on startup
        this.checkHealth().subscribe();
    }

    /**
     * Get the current update status as an observable
     */
    get status$(): Observable<UpdateStatus | null> {
        return this._status$.asObservable();
    }

    /**
     * Whether an update server is available
     */
    get updateAvailable$(): Observable<boolean> {
        return this._updateAvailable$.asObservable();
    }

    /**
     * Check if the update server is reachable and configured
     */
    checkHealth(): Observable<UpdateHealthCheck> {
        return this._http.get<UpdateHealthCheck>(`${this.BASE_URL}/health`).pipe(
            map(response => {
                this._updateAvailable$.next(response.available && response.configured);
                this._logger.debug("Update server health:", response);
                return response;
            }),
            catchError(err => {
                this._logger.warn("Update server health check failed:", err);
                this._updateAvailable$.next(false);
                return [{
                    available: false,
                    configured: false,
                    error: err.message
                }];
            })
        );
    }

    /**
     * Get current update status from the server
     */
    getStatus(): Observable<UpdateStatus> {
        return this._http.get<UpdateStatus>(`${this.BASE_URL}/status`).pipe(
            map(response => {
                this._status$.next(response);
                return response;
            }),
            catchError(err => {
                this._logger.error("Failed to get update status:", err);
                throw err;
            })
        );
    }

    /**
     * Trigger an update
     */
    triggerUpdate(): Observable<{ message: string; started_at: string }> {
        this._logger.info("Triggering update...");
        
        return this._http.get<{ message: string; started_at: string }>(`${this.BASE_URL}/trigger`).pipe(
            map(response => {
                this._logger.info("Update triggered:", response);
                
                // Show notification
                this._notifService.show(new Notification({
                    level: Notification.Level.INFO,
                    dismissible: true,
                    text: "Update started. RapidCopy will restart when complete."
                }));
                
                // Start polling for status
                this.startPolling();
                
                return response;
            }),
            catchError((err: HttpErrorResponse) => {
                let errorMessage = "Failed to trigger update";
                
                if (err.status === 409) {
                    errorMessage = "An update is already in progress";
                } else if (err.status === 503) {
                    errorMessage = "Update service not configured";
                } else if (err.error?.error) {
                    errorMessage = err.error.error;
                }
                
                this._logger.error("Update trigger failed:", errorMessage);
                
                this._notifService.show(new Notification({
                    level: Notification.Level.DANGER,
                    dismissible: true,
                    text: errorMessage
                }));
                
                throw new Error(errorMessage);
            })
        );
    }

    /**
     * Start polling for update status
     */
    private startPolling(): void {
        if (this._isPolling) {
            return;
        }
        
        this._isPolling = true;
        this._logger.debug("Starting update status polling");
        
        // Poll every 2 seconds
        timer(0, 2000).pipe(
            takeWhile(() => this._isPolling),
            switchMap(() => this.getStatus()),
            takeWhile(status => status.status === "updating", true),
            finalize(() => {
                this._isPolling = false;
                this._logger.debug("Update status polling stopped");
            })
        ).subscribe({
            next: status => {
                if (status.status === "success") {
                    this._notifService.show(new Notification({
                        level: Notification.Level.SUCCESS,
                        dismissible: true,
                        text: "Update completed successfully! The page will reload shortly."
                    }));
                    
                    // Wait a bit for container to restart, then reload
                    setTimeout(() => {
                        window.location.reload();
                    }, 10000);
                    
                } else if (status.status === "failed") {
                    this._notifService.show(new Notification({
                        level: Notification.Level.DANGER,
                        dismissible: true,
                        text: `Update failed: ${status.message}`
                    }));
                }
            },
            error: err => {
                // Connection lost - container might be restarting
                this._logger.info("Lost connection during update (expected during restart)");
                
                // Try to reconnect after a delay
                setTimeout(() => {
                    this.waitForReconnect();
                }, 5000);
            }
        });
    }

    /**
     * Stop polling
     */
    stopPolling(): void {
        this._isPolling = false;
    }

    /**
     * Wait for the server to come back after restart
     */
    private waitForReconnect(): void {
        this._logger.info("Waiting for server to restart...");
        
        const maxAttempts = 30; // 30 attempts * 2 seconds = 1 minute
        let attempts = 0;
        
        const tryReconnect = () => {
            attempts++;
            
            this._http.get<UpdateHealthCheck>(`${this.BASE_URL}/health`).subscribe({
                next: () => {
                    this._logger.info("Server is back online!");
                    this._notifService.show(new Notification({
                        level: Notification.Level.SUCCESS,
                        dismissible: true,
                        text: "Update completed! Reloading..."
                    }));
                    
                    setTimeout(() => {
                        window.location.reload();
                    }, 1000);
                },
                error: () => {
                    if (attempts < maxAttempts) {
                        setTimeout(tryReconnect, 2000);
                    } else {
                        this._notifService.show(new Notification({
                            level: Notification.Level.WARNING,
                            dismissible: true,
                            text: "Server is taking longer than expected. Please refresh manually."
                        }));
                    }
                }
            });
        };
        
        tryReconnect();
    }
}
