import {Record} from "immutable";

interface INotification {
    level: Notification.Level;
    text: string;
    timestamp: number;
    dismissible: boolean;
}
const DefaultNotification: INotification = {
    level: null,
    text: null,
    timestamp: null,
    dismissible: false,
};
const NotificationRecord = Record(DefaultNotification);


export class Notification extends NotificationRecord implements INotification {
    constructor(props) {
        props.timestamp = Date.now();
        super(props);
    }

    // Use getters to properly access Record values (Immutable.js 4.x compatibility)
    get level(): Notification.Level {
        return this.get("level");
    }

    get text(): string {
        return this.get("text");
    }

    get timestamp(): number {
        return this.get("timestamp");
    }

    get dismissible(): boolean {
        return this.get("dismissible");
    }
}


export module Notification {
    export enum Level {
        SUCCESS         = <any> "success",
        INFO            = <any> "info",
        WARNING         = <any> "warning",
        DANGER          = <any> "danger",
    }
}
