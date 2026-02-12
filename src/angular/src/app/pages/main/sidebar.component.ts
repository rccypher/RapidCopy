import {Component, OnDestroy, OnInit} from "@angular/core";
import {Subject} from "rxjs";
import {takeUntil} from "rxjs/operators";

import {ROUTE_INFOS} from "../../routes";
import {ServerCommandService} from "../../services/server/server-command.service";
import {LoggerService} from "../../services/utils/logger.service";
import {ConnectedService} from "../../services/utils/connected.service";
import {StreamServiceRegistry} from "../../services/base/stream-service.registry";
import {ThemeService, Theme} from "../../services/utils/theme.service";

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
                private _themeService: ThemeService) {
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
        this._commandService.restart().subscribe({
            next: reaction => {
                if (reaction.success) {
                    this._logger.info(reaction.data);
                } else {
                    this._logger.error(reaction.errorMessage);
                }
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
