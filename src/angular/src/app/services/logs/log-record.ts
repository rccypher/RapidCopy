import {Record} from "immutable";


/**
 * LogRecord immutable
 */
interface ILogRecord {
    time: Date;
    level: LogRecord.Level;
    loggerName: string;
    message: string;
    exceptionTraceback: string;
}
const DefaultLogRecord: ILogRecord = {
    time: null,
    level: null,
    loggerName: null,
    message: null,
    exceptionTraceback: null,
};
const LogRecordRecord = Record(DefaultLogRecord);
export class LogRecord extends LogRecordRecord implements ILogRecord {
    constructor(props) {
        super(props);
    }

    // Use getters to properly access Record values (Immutable.js 4.x compatibility)
    get time(): Date { return this.get("time"); }
    get level(): LogRecord.Level { return this.get("level"); }
    get loggerName(): string { return this.get("loggerName"); }
    get message(): string { return this.get("message"); }
    get exceptionTraceback(): string { return this.get("exceptionTraceback"); }
}


export module LogRecord {
    export function fromJson(json: LogRecordJson): LogRecord {
        return new LogRecord({
            // str -> number, then sec -> ms
            time: new Date(1000 * +json.time),
            level: LogRecord.Level[json.level_name],
            loggerName: json.logger_name,
            message: json.message,
            exceptionTraceback: json.exc_tb
        });
    }

    export enum Level {
        DEBUG       = <any> "DEBUG",
        INFO        = <any> "INFO",
        WARNING     = <any> "WARNING",
        ERROR       = <any> "ERROR",
        CRITICAL    = <any> "CRITICAL",
    }
}


/**
 * LogRecord as serialized by the backend.
 * Note: naming convention matches that used in JSON
 */
export interface LogRecordJson {
    time: number;
    level_name: string;
    logger_name: string;
    message: string;
    exc_tb: string;
}
