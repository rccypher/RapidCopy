export class Localization {
    // Escape untrusted values before embedding them in notification HTML that is
    // rendered via [innerHTML]. The surrounding tags (<br/>, <a>) are intentional;
    // only interpolated server-provided data must be escaped to prevent XSS.
    static escapeHtml(s: string): string {
        return String(s == null ? "" : s)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    static Error = class {
        public static readonly SERVER_DISCONNECTED = "Lost connection to the RapidCopy service.";
    };

    static Notification = class {
        public static readonly CONFIG_RESTART = "Restart the app to apply new settings.";
        public static readonly CONFIG_VALUE_BLANK =
            (section: string, option: string) => `Setting ${section}.${option} cannot be blank.`

        public static readonly AUTOQUEUE_PATTERN_EMPTY = "Cannot add an empty autoqueue pattern.";

        public static readonly STATUS_CONNECTION_WAITING = "Waiting for RapidCopy service to respond...";
        public static readonly STATUS_REMOTE_SCAN_WAITING = "Waiting for remote server to respond...";
        public static readonly STATUS_REMOTE_SERVER_ERROR = (error: string) =>
            `Lost connection to remote server. Retrying automatically. \
             ${error ? "<br />" + Localization.escapeHtml(error) : ""}`

        public static readonly NEW_VERSION_AVAILABLE = (url: string) =>
            `A new version of RapidCopy is available! \
             Click <a href="${Localization.escapeHtml(url)}" target="blank">here</a> to grab the latest version.`
    };

    static Modal = class {
        public static readonly DELETE_LOCAL_TITLE = "Delete Local File";
        public static readonly DELETE_LOCAL_MESSAGE =
            (name: string) => `Are you sure you want to delete <b>${name}</b> from the local server?`

        public static readonly DELETE_REMOTE_TITLE = "Delete Remote File";
        public static readonly DELETE_REMOTE_MESSAGE =
            (name: string) => `Are you sure you want to delete <b>${name}</b> from the remote server?`
    };

    static Log = class {
        public static readonly CONNECTED = "Connected to service";
        public static readonly DISCONNECTED = "Lost connection to service";
    };
}
