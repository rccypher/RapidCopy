import {Injectable, NgZone} from "@angular/core";
import {Observable, Subscription} from "rxjs";

import {ModelFileService} from "../files/model-file.service";
import {ServerStatusService} from "../server/server-status.service";
import {LoggerService} from "../utils/logger.service";
import {ConnectedService} from "../utils/connected.service";
import {ApiKeyInterceptor} from "../utils/api-key.interceptor";
import {LogService} from "../logs/log.service";


export class EventSourceFactory {
    static createEventSource(url: string): EventSource {
        return new EventSource(url);
    }
}


export interface IStreamService {
    /**
     * Returns the event names supported by this stream service
     * @returns {string[]}
     */
    getEventNames(): string[];

    /**
     * Notifies the stream service that it is now connected
     */
    notifyConnected();

    /**
     * Notifies the stream service that it is now disconnected
     */
    notifyDisconnected();

    /**
     * Notifies the stream service of an event
     * @param {string} eventName
     * @param {string} data
     */
    notifyEvent(eventName: string, data: string);
}


/**
 * StreamDispatchService is the top-level service that connects to
 * the multiplexed SSE stream. It listens for SSE events and dispatches
 * them to whichever IStreamService that requested them.
 */
@Injectable()
export class StreamDispatchService {
    private readonly STREAM_URL = "/server/stream";

    private readonly STREAM_RETRY_INTERVAL_MS = 3000;

    private _eventNameToServiceMap: Map<string, IStreamService> = new Map();
    private _services: IStreamService[] = [];

    private _subscription: Subscription = null;
    private _reconnectHandle: any = null;

    constructor(private _logger: LoggerService,
                private _zone: NgZone) {
    }

    /**
     * Call this method to finish initialization
     */
    public onInit() {
        this.createSseObserver();
    }

    /**
     * Register an IStreamService with the dispatch
     * @param {IStreamService} service
     * @returns {IStreamService}
     */
    public registerService(service: IStreamService) {
        for(let eventName of service.getEventNames()) {
            this._eventNameToServiceMap.set(eventName, service);
        }
        this._services.push(service);
        return service;
    }

    private createSseObserver() {
        // Defensive: tear down any previous subscription/EventSource before opening a
        // new one, so a reconnect can never leave two live streams running in parallel.
        if (this._subscription) {
            this._subscription.unsubscribe();
            this._subscription = null;
        }
        const observable = new Observable(observer => {
            // EventSource cannot set request headers, so the API key is passed as a
            // query param (the backend accepts ?apikey= on the stream route).
            const apiKey = ApiKeyInterceptor.getApiKey();
            const url = apiKey
                ? `${this.STREAM_URL}?apikey=${encodeURIComponent(apiKey)}`
                : this.STREAM_URL;
            const eventSource = EventSourceFactory.createEventSource(url);
            for (let eventName of Array.from(this._eventNameToServiceMap.keys())) {
                eventSource.addEventListener(eventName, event => observer.next(
                    {
                        "event": eventName,
                        "data": (<MessageEvent>event).data
                    }
                ));
            }

            // noinspection SpellCheckingInspection
            // noinspection JSUnusedLocalSymbols
            eventSource.onopen = event => {
                this._logger.info("Connected to server stream");

                // Notify all services of connection
                for (let service of this._services) {
                    this._zone.run(() => {
                        service.notifyConnected();
                    });
                }
            };

            eventSource.onerror = x => {
                // EventSource fires onerror for transient drops too and then
                // auto-reconnects on its own (readyState === CONNECTING). Only
                // treat a permanently CLOSED stream as a real error; let the
                // browser silently recover from transient blips instead of
                // flapping the whole UI to "disconnected" and forcing a reconnect.
                if (eventSource.readyState === EventSource.CLOSED) {
                    observer.error(x);
                }
            };

            return () => {
                eventSource.close();
            };
        });
        this._subscription = observable.subscribe({
            next: (x: any) => {
                let eventName = x["event"];
                let eventData = x["data"];
                // this._logger.debug("Received event:", eventName);
                this._zone.run(() => {
                    const service = this._eventNameToServiceMap.get(eventName);
                    if (service) {
                        service.notifyEvent(eventName, eventData);
                    }
                });
            },
            error: err => {
                this._logger.error("Error in stream: %O", err);

                // Notify all services of disconnection
                for (let service of this._services) {
                    this._zone.run(() => {
                        service.notifyDisconnected();
                    });
                }

                // Schedule a single reconnect; clear any pending one first so
                // repeated errors can't stack multiple reconnect timers.
                if (this._reconnectHandle) {
                    clearTimeout(this._reconnectHandle);
                }
                this._reconnectHandle = setTimeout(() => {
                    this._reconnectHandle = null;
                    this.createSseObserver();
                }, this.STREAM_RETRY_INTERVAL_MS);
            }
        });
    }
}


/**
 * StreamServiceRegistry is responsible for initializing all
 * Stream Services. All services created by the registry
 * will be connected to a single stream via the DispatchService
 */
@Injectable()
export class StreamServiceRegistry {

    constructor(private _dispatch: StreamDispatchService,
                private _modelFileService: ModelFileService,
                private _serverStatusService: ServerStatusService,
                private _connectedService: ConnectedService,
                private _logService: LogService) {
        // Register all services
        _dispatch.registerService(_connectedService);
        _dispatch.registerService(_serverStatusService);
        _dispatch.registerService(_modelFileService);
        _dispatch.registerService(_logService);
    }

    /**
     * Call this method to finish initialization
     */
    public onInit() {
        this._dispatch.onInit();
    }

    get modelFileService(): ModelFileService { return this._modelFileService; }
    get serverStatusService(): ServerStatusService { return this._serverStatusService; }
    get connectedService(): ConnectedService { return this._connectedService; }
    get logService(): LogService { return this._logService; }
}

/**
 * StreamServiceRegistry factory and provider
 */
export let streamServiceRegistryFactory = (
        _dispatch: StreamDispatchService,
        _modelFileService: ModelFileService,
        _serverStatusService: ServerStatusService,
        _connectedService: ConnectedService,
        _logService: LogService
) => {
    let streamServiceRegistry = new StreamServiceRegistry(
        _dispatch,
        _modelFileService,
        _serverStatusService,
        _connectedService,
        _logService
    );
    streamServiceRegistry.onInit();
    return streamServiceRegistry;
};

// noinspection JSUnusedGlobalSymbols
export let StreamServiceRegistryProvider = {
    provide: StreamServiceRegistry,
    useFactory: streamServiceRegistryFactory,
    deps: [
        StreamDispatchService,
        ModelFileService,
        ServerStatusService,
        ConnectedService,
        LogService
    ]
};
