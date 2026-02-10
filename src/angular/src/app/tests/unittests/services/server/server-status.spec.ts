import * as Immutable from "immutable";

import {ServerStatus, ServerStatusJson} from "../../../../services/server/server-status";


describe("Testing log record initialization", () => {
    let baseJson: ServerStatusJson;
    let baseStatus: ServerStatus;

    beforeEach(() => {
        baseJson = {
            server: {
                up: true,
                error_msg: "An error message"
            },
            controller: {
                latest_local_scan_time: "1514776875.9439101",
                latest_remote_scan_time: "1524743857.3456243",
                latest_remote_scan_failed: true,
                latest_remote_scan_error: "message failure reason",
                downloads_paused_disk_space: false,
                disk_space_error: null
            }
        };
        baseStatus = ServerStatus.fromJson(baseJson);
    });

    it("should be immutable", () => {
        expect(baseStatus instanceof Immutable.Record).toBe(true);
    });

    it("should correctly initialize server up", () => {
        expect(baseStatus.server.up).toBe(true);
    });

    it("should correctly initialize server error message", () => {
        expect(baseStatus.server.errorMessage).toBe("An error message");
    });

    it("should correctly initialize controller latest local scan time", () => {
        expect(baseStatus.controller.latestLocalScanTime).toEqual(new Date(1514776875943));
        // Allow null
        baseJson.controller.latest_local_scan_time = null;
        const newStatus = ServerStatus.fromJson(baseJson);
        expect(newStatus.controller.latestLocalScanTime).toBeNull();
    });

    it("should correctly initialize controller latest remote scan time", () => {
        expect(baseStatus.controller.latestRemoteScanTime).toEqual(new Date(1524743857345));
        // Allow null
        baseJson.controller.latest_remote_scan_time = null;
        const newStatus = ServerStatus.fromJson(baseJson);
        expect(newStatus.controller.latestRemoteScanTime).toBeNull();
    });

    it("should correctly initialize controller failure", () => {
        expect(baseStatus.controller.latestRemoteScanFailed).toBe(true);
    });

    it("should correctly initialize controller error", () => {
        expect(baseStatus.controller.latestRemoteScanError).toBe("message failure reason");
    });

    it("should correctly initialize downloads paused disk space", () => {
        expect(baseStatus.controller.downloadsPausedDiskSpace).toBe(false);
        // Test true value
        baseJson.controller.downloads_paused_disk_space = true;
        const newStatus = ServerStatus.fromJson(baseJson);
        expect(newStatus.controller.downloadsPausedDiskSpace).toBe(true);
    });

    it("should correctly initialize disk space error", () => {
        expect(baseStatus.controller.diskSpaceError).toBeNull();
        // Test with error message
        baseJson.controller.disk_space_error = "Low disk space on /data (5.2% free, threshold 10%)";
        const newStatus = ServerStatus.fromJson(baseJson);
        expect(newStatus.controller.diskSpaceError).toBe("Low disk space on /data (5.2% free, threshold 10%)");
    });

    it("should handle null disk space fields", () => {
        baseJson.controller.downloads_paused_disk_space = null;
        baseJson.controller.disk_space_error = null;
        const newStatus = ServerStatus.fromJson(baseJson);
        expect(newStatus.controller.downloadsPausedDiskSpace).toBeNull();
        expect(newStatus.controller.diskSpaceError).toBeNull();
    });
});
