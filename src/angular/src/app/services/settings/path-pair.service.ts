import {Injectable} from "@angular/core";
import {HttpClient} from "@angular/common/http";
import {Observable, BehaviorSubject} from "rxjs";
import {map, tap} from "rxjs/operators";

/**
 * PathPair model for multiple source/destination directory support
 */
export interface PathPair {
    id: string;
    name: string;
    remote_path: string;
    local_path: string;
    enabled: boolean;
    auto_queue: boolean;
}

export interface PathPairResponse {
    success: boolean;
    data?: PathPair | PathPair[];
    error?: string;
}

/**
 * Service for managing path pairs (multiple source/destination directories)
 */
@Injectable({
    providedIn: "root"
})
export class PathPairService {
    private readonly baseUrl = "/server/path-pairs";
    
    // BehaviorSubject to allow components to subscribe to path pair changes
    private _pathPairs$ = new BehaviorSubject<PathPair[]>([]);
    public pathPairs$ = this._pathPairs$.asObservable();

    constructor(private http: HttpClient) {
        // Load path pairs on service initialization
        this.refresh();
    }

    /**
     * Refresh the path pairs list from the server
     */
    refresh(): void {
        this.getAll().subscribe({
            next: (pairs) => this._pathPairs$.next(pairs),
            error: (err) => console.error("Failed to load path pairs:", err)
        });
    }

    /**
     * Get all path pairs
     */
    getAll(): Observable<PathPair[]> {
        return this.http.get<PathPairResponse>(this.baseUrl).pipe(
            map(response => {
                if (response.success && Array.isArray(response.data)) {
                    return response.data;
                }
                throw new Error(response.error || "Failed to get path pairs");
            })
        );
    }

    /**
     * Get a single path pair by ID
     */
    getById(id: string): Observable<PathPair> {
        return this.http.get<PathPairResponse>(`${this.baseUrl}/${id}`).pipe(
            map(response => {
                if (response.success && response.data && !Array.isArray(response.data)) {
                    return response.data;
                }
                throw new Error(response.error || "Failed to get path pair");
            })
        );
    }

    /**
     * Create a new path pair
     */
    create(pair: Omit<PathPair, "id">): Observable<PathPair> {
        return this.http.post<PathPairResponse>(this.baseUrl, pair).pipe(
            map(response => {
                if (response.success && response.data && !Array.isArray(response.data)) {
                    return response.data;
                }
                throw new Error(response.error || "Failed to create path pair");
            }),
            tap(() => this.refresh())
        );
    }

    /**
     * Update an existing path pair
     */
    update(pair: PathPair): Observable<PathPair> {
        return this.http.put<PathPairResponse>(`${this.baseUrl}/${pair.id}`, pair).pipe(
            map(response => {
                if (response.success && response.data && !Array.isArray(response.data)) {
                    return response.data;
                }
                throw new Error(response.error || "Failed to update path pair");
            }),
            tap(() => this.refresh())
        );
    }

    /**
     * Delete a path pair
     */
    delete(id: string): Observable<void> {
        return this.http.delete<PathPairResponse>(`${this.baseUrl}/${id}`).pipe(
            map(response => {
                if (!response.success) {
                    throw new Error(response.error || "Failed to delete path pair");
                }
            }),
            tap(() => this.refresh())
        );
    }

    /**
     * Reorder path pairs
     */
    reorder(ids: string[]): Observable<PathPair[]> {
        return this.http.post<PathPairResponse>(`${this.baseUrl}/reorder`, { order: ids }).pipe(
            map(response => {
                if (response.success && Array.isArray(response.data)) {
                    return response.data;
                }
                throw new Error(response.error || "Failed to reorder path pairs");
            }),
            tap((pairs) => this._pathPairs$.next(pairs))
        );
    }

    /**
     * Get the current path pairs value (synchronous)
     */
    getCurrentPairs(): PathPair[] {
        return this._pathPairs$.getValue();
    }

    /**
     * Get enabled path pairs only
     */
    getEnabledPairs(): PathPair[] {
        return this._pathPairs$.getValue().filter(p => p.enabled);
    }
}
