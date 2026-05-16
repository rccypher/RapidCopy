import {Injectable} from "@angular/core";
import {HttpClient, HttpParams} from "@angular/common/http";
import {Observable} from "rxjs";
import {map} from "rxjs/operators";
import {LogRecord, LogRecordJson} from "./log-record";


export interface LogQueryResult {
    records: LogRecord[];
    truncated: boolean;
}

@Injectable({providedIn: "root"})
export class LogQueryService {

    constructor(private _http: HttpClient) {}

    search(params: {
        search?: string;
        level?: string;
        limit?: number;
        before?: number;
    }): Observable<LogQueryResult> {
        let httpParams = new HttpParams();
        if (params.search) { httpParams = httpParams.set("search", params.search); }
        if (params.level)  { httpParams = httpParams.set("level",  params.level);  }
        if (params.limit)  { httpParams = httpParams.set("limit",  String(params.limit)); }
        if (params.before) { httpParams = httpParams.set("before", String(params.before)); }

        return this._http.get<{records: LogRecordJson[], truncated: boolean}>(
            "/server/logs", {params: httpParams}
        ).pipe(
            map(body => ({
                records: body.records.map(r => LogRecord.fromJson(r)),
                truncated: body.truncated
            }))
        );
    }
}
