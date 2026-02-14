import {Injectable} from "@angular/core";
import {HttpClient} from "@angular/common/http";
import {Observable, BehaviorSubject} from "rxjs";
import {map, tap} from "rxjs/operators";

/**
 * NetworkMount model for network share mounting support
 */
export interface NetworkMount {
    id: string;
    name: string;
    mount_type: "nfs" | "cifs" | "local";
    enabled: boolean;
    server: string;
    share_path: string;
    username: string | null;
    password: string | null;
    domain: string | null;
    mount_options: string;
    mount_point: string;
    mount_source: string;
    status: "mounted" | "unmounted" | "error" | "unknown";
    status_message: string;
}

export interface NetworkMountResponse {
    success: boolean;
    data?: NetworkMount | NetworkMount[];
    error?: string;
    warnings?: string[];
}

export interface MountActionResponse {
    success: boolean;
    data?: {
        message?: string;
        connected?: boolean;
    };
    error?: string;
}

/**
 * Result of a create/update operation, including any validation warnings
 */
export interface NetworkMountResult {
    mount: NetworkMount;
    warnings: string[];
}

/**
 * Service for managing network mounts (NFS/CIFS shares)
 */
@Injectable({
    providedIn: "root"
})
export class NetworkMountService {
    private readonly baseUrl = "/server/mounts";
    
    // BehaviorSubject to allow components to subscribe to mount changes
    private _mounts$ = new BehaviorSubject<NetworkMount[]>([]);
    public mounts$ = this._mounts$.asObservable();

    constructor(private http: HttpClient) {
        // Load mounts on service initialization
        this.refresh();
    }

    /**
     * Refresh the mounts list from the server
     */
    refresh(): void {
        this.getAll().subscribe({
            next: (mounts) => this._mounts$.next(mounts),
            error: (err) => console.error("Failed to load network mounts:", err)
        });
    }

    /**
     * Get all network mounts with their current status
     */
    getAll(): Observable<NetworkMount[]> {
        return this.http.get<NetworkMountResponse>(this.baseUrl).pipe(
            map(response => {
                if (response.success && Array.isArray(response.data)) {
                    return response.data;
                }
                throw new Error(response.error || "Failed to get network mounts");
            })
        );
    }

    /**
     * Get a single network mount by ID
     */
    getById(id: string): Observable<NetworkMount> {
        return this.http.get<NetworkMountResponse>(`${this.baseUrl}/${id}`).pipe(
            map(response => {
                if (response.success && response.data && !Array.isArray(response.data)) {
                    return response.data;
                }
                throw new Error(response.error || "Failed to get network mount");
            })
        );
    }

    /**
     * Create a new network mount
     * Returns the created mount along with any validation warnings
     */
    create(mount: Omit<NetworkMount, "id" | "mount_point" | "mount_source" | "status" | "status_message">): Observable<NetworkMountResult> {
        return this.http.post<NetworkMountResponse>(this.baseUrl, mount).pipe(
            map(response => {
                if (response.success && response.data && !Array.isArray(response.data)) {
                    return {
                        mount: response.data,
                        warnings: response.warnings || []
                    };
                }
                throw new Error(response.error || "Failed to create network mount");
            }),
            tap(() => this.refresh())
        );
    }

    /**
     * Update an existing network mount
     * Returns the updated mount along with any validation warnings
     */
    update(mount: Partial<NetworkMount> & {id: string}): Observable<NetworkMountResult> {
        return this.http.put<NetworkMountResponse>(`${this.baseUrl}/${mount.id}`, mount).pipe(
            map(response => {
                if (response.success && response.data && !Array.isArray(response.data)) {
                    return {
                        mount: response.data,
                        warnings: response.warnings || []
                    };
                }
                throw new Error(response.error || "Failed to update network mount");
            }),
            tap(() => this.refresh())
        );
    }

    /**
     * Delete a network mount
     */
    delete(id: string): Observable<void> {
        return this.http.delete<NetworkMountResponse>(`${this.baseUrl}/${id}`).pipe(
            map(response => {
                if (!response.success) {
                    throw new Error(response.error || "Failed to delete network mount");
                }
            }),
            tap(() => this.refresh())
        );
    }

    /**
     * Mount the specified share
     */
    mount(id: string): Observable<string> {
        return this.http.post<MountActionResponse>(`${this.baseUrl}/${id}/mount`, {}).pipe(
            map(response => {
                if (response.success) {
                    return response.data?.message || "Mount successful";
                }
                throw new Error(response.error || "Failed to mount");
            }),
            tap(() => this.refresh())
        );
    }

    /**
     * Unmount the specified share
     */
    unmount(id: string, force: boolean = false): Observable<string> {
        return this.http.post<MountActionResponse>(`${this.baseUrl}/${id}/unmount`, {force}).pipe(
            map(response => {
                if (response.success) {
                    return response.data?.message || "Unmount successful";
                }
                throw new Error(response.error || "Failed to unmount");
            }),
            tap(() => this.refresh())
        );
    }

    /**
     * Test connectivity to the mount server
     */
    testConnection(id: string): Observable<{connected: boolean; message: string}> {
        return this.http.get<MountActionResponse>(`${this.baseUrl}/${id}/test`).pipe(
            map(response => {
                if (response.success && response.data) {
                    return {
                        connected: response.data.connected || false,
                        message: response.data.message || ""
                    };
                }
                throw new Error(response.error || "Failed to test connection");
            })
        );
    }

    /**
     * Get the current mounts value (synchronous)
     */
    getCurrentMounts(): NetworkMount[] {
        return this._mounts$.getValue();
    }

    /**
     * Get enabled mounts only
     */
    getEnabledMounts(): NetworkMount[] {
        return this._mounts$.getValue().filter(m => m.enabled);
    }

    /**
     * Get mounted mounts only
     */
    getMountedMounts(): NetworkMount[] {
        return this._mounts$.getValue().filter(m => m.status === "mounted");
    }
}
