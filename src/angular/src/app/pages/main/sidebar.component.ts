import {Component, OnInit} from "@angular/core";

import {ROUTE_INFOS} from "../../routes";
import {ServerCommandService} from "../../services/server/server-command.service";
import {LoggerService} from "../../services/utils/logger.service";
import {ConnectedService} from "../../services/utils/connected.service";
import {StreamServiceRegistry} from "../../services/base/stream-service.registry";

@Component({
    selector: "app-sidebar",
    templateUrl: "./sidebar.component.html",
    styleUrls: ["./sidebar.component.scss"]
})

export class SidebarComponent implements OnInit {
    routeInfos = ROUTE_INFOS;

    public commandsEnabled: boolean;
    public isDarkTheme: boolean;

    private _connectedService: ConnectedService;

    private static readonly THEME_KEY = "seedsync-dark-theme";

    constructor(private _logger: LoggerService,
                _streamServiceRegistry: StreamServiceRegistry,
                private _commandService: ServerCommandService) {
        this._connectedService = _streamServiceRegistry.connectedService;
        this.commandsEnabled = false;
        this.isDarkTheme = localStorage.getItem(SidebarComponent.THEME_KEY) === "true";
        this._applyTheme();
    }

    // noinspection JSUnusedGlobalSymbols
    ngOnInit() {
        this._connectedService.connected.subscribe({
            next: (connected: boolean) => {
                this.commandsEnabled = connected;
            }
        });
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
        this.isDarkTheme = !this.isDarkTheme;
        localStorage.setItem(SidebarComponent.THEME_KEY, String(this.isDarkTheme));
        this._applyTheme();
    }

    private _applyTheme() {
        if (this.isDarkTheme) {
            document.body.classList.add("dark-theme");
        } else {
            document.body.classList.remove("dark-theme");
        }
    }
}
