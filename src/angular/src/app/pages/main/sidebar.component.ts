import {Component, OnDestroy, OnInit} from "@angular/core";
import {Subject} from "rxjs";
import {takeUntil} from "rxjs/operators";

import {ROUTE_INFOS} from "../../routes";
import {ServerCommandService} from "../../services/server/server-command.service";
import {LoggerService} from "../../services/utils/logger.service";
import {ConnectedService} from "../../services/utils/connected.service";
import {StreamServiceRegistry} from "../../services/base/stream-service.registry";
import {ThemeService, Theme} from "../../services/utils/theme.service";
import {NotificationService} from "../../services/utils/notification.service";
import {Notification} from "../../services/utils/notification";

@Component({
    selector: "app-sidebar",
    templateUrl: "./sidebar.component.html",
    styleUrls: ["./sidebar.component.scss"]
})

export class SidebarComponent implements OnInit, OnDestroy {
    routeInfos = ROUTE_INFOS;

    public commandsEnabled: boolean;
    public currentTheme: Theme = 'light';

    private _connectedService: ConnectedService;
    private destroy$ = new Subject<void>();

    constructor(private _logger: LoggerService,
                _streamServiceRegistry: StreamServiceRegistry,
                private _commandService: ServerCommandService,
                private _themeService: ThemeService,
                private _notifService: NotificationService) {
        this._connectedService = _streamServiceRegistry.connectedService;
        this.commandsEnabled = false;
    }

    // noinspection JSUnusedGlobalSymbols
    ngOnInit() {
        this._connectedService.connected
            .pipe(takeUntil(this.destroy$))
            .subscribe({
                next: (connected: boolean) => {
                    this.commandsEnabled = connected;
                }
            });

        this._themeService.theme$
            .pipe(takeUntil(this.destroy$))
            .subscribe({
                next: (theme: Theme) => {
                    this.currentTheme = theme;
                }
            });
    }

    ngOnDestroy() {
        this.destroy$.next();
        this.destroy$.complete();
    }

    onCommandRestart() {
        // Show immediate feedback that restart is being initiated
        const restartingNotif = new Notification({
            level: Notification.Level.INFO,
            text: "Restarting server...",
            dismissible: false
        });
        this._notifService.show(restartingNotif);

        this._commandService.restart().subscribe({
            next: reaction => {
                // Hide the "restarting" notification
                this._notifService.hide(restartingNotif);

                if (reaction.success) {
                    this._logger.info(reaction.data);
                    // Show success notification
                    this._notifService.show(new Notification({
                        level: Notification.Level.SUCCESS,
                        text: "Server restart initiated successfully. The page will reconnect automatically.",
                        dismissible: true
                    }));
                } else {
                    this._logger.error(reaction.errorMessage);
                    // Show error notification
                    this._notifService.show(new Notification({
                        level: Notification.Level.DANGER,
                        text: `Restart failed: ${reaction.errorMessage}`,
                        dismissible: true
                    }));
                }
            },
            error: (err) => {
                // Hide the "restarting" notification
                this._notifService.hide(restartingNotif);

                // Connection error during restart is expected (server went down)
                // Show informational message instead of error
                this._notifService.show(new Notification({
                    level: Notification.Level.INFO,
                    text: "Server is restarting. The page will reconnect automatically when ready.",
                    dismissible: true
                }));
            }
        });
    }

    onToggleTheme() {
        this._themeService.toggleTheme();
    }

    get isDarkMode(): boolean {
        return this.currentTheme === 'dark';
    }
}
