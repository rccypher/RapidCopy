import {Injectable} from "@angular/core";
import {Observable} from "rxjs";
import {ReplaySubject} from "rxjs";

import {BaseStreamService} from "../base/base-stream.service";
import {LogRecord} from "./log-record";


@Injectable()
export class LogService extends BaseStreamService {

    // Cap the replay buffer: an unbounded ReplaySubject would retain every log
    // record for the whole session and replay all of them to each new subscriber.
    private _logs: ReplaySubject<LogRecord> = new ReplaySubject(500);

    constructor() {
        super();
        this.registerEventName("log-record");
    }

    /**
     * Logs is a hot observable (i.e. no caching)
     * @returns {Observable<LogRecord>}
     */
    get logs(): Observable<LogRecord> {
        return this._logs.asObservable();
    }

    protected onEvent(eventName: string, data: string) {
        this._logs.next(LogRecord.fromJson(JSON.parse(data)));
    }

    protected onConnected() {
        // nothing to do
    }

    protected onDisconnected() {
        // nothing to do
    }

}
