import {Component, ChangeDetectionStrategy, NgZone, OnInit, OnDestroy} from "@angular/core";
import {CommonModule} from "@angular/common";
import {Observable, Subject, combineLatest} from "rxjs";
import {map, takeUntil} from "rxjs/operators";

import * as Immutable from "immutable";

import {ViewFileService} from "../../services/files/view-file.service";
import {ViewFile} from "../../services/files/view-file";
import {PathPairService, PathPair} from "../../services/settings/path-pair.service";
import {FileSizePipe} from "../../common/file-size.pipe";

/**
 * Statistics for a single path pair
 */
export interface PathPairStat {
    pathPairId: string;
    pathPairName: string;
    remotePath: string;
    localPath: string;
    totalFiles: number;
    downloadingCount: number;
    queuedCount: number;
    downloadedCount: number;
    totalRemoteSize: number;
    // Bytes transferred: remoteSize of completed files + localSize of in-progress files.
    // Does NOT use raw local disk usage (which can exceed remote size due to extraction, stale files etc.)
    totalTransferredSize: number;
    totalSpeed: number;
    overallProgress: number;
}

/**
 * Component that displays transfer statistics grouped by path pair.
 * Uses the async pipe for all data to ensure OnPush change detection fires correctly
 * even when SSE callbacks arrive outside Angular's zone.
 */
@Component({
    selector: "app-path-pair-stats",
    standalone: true,
    imports: [CommonModule, FileSizePipe],
    templateUrl: "./path-pair-stats.component.html",
    styleUrls: ["./path-pair-stats.component.scss"],
    changeDetection: ChangeDetectionStrategy.OnPush
})
export class PathPairStatsComponent implements OnInit, OnDestroy {
    stats$: Observable<PathPairStat[]>;
    hasMultiplePathPairs$: Observable<boolean>;
    isExpanded = true;

    private destroy$ = new Subject<void>();

    constructor(
        private viewFileService: ViewFileService,
        private pathPairService: PathPairService,
        private ngZone: NgZone
    ) {}

    ngOnInit(): void {
        // combineLatest re-emits whenever either source emits.
        // The async pipe handles zone re-entry so OnPush change detection fires
        // correctly even when SSE callbacks arrive outside Angular's zone.
        this.stats$ = combineLatest([
            this.pathPairService.pathPairs$,
            this.viewFileService.files
        ]).pipe(
            takeUntil(this.destroy$),
            map(([pairs, files]) => this.computeStats(pairs, files))
        );

        this.hasMultiplePathPairs$ = this.pathPairService.pathPairs$.pipe(
            takeUntil(this.destroy$),
            map(pairs => pairs.length > 1)
        );
    }

    ngOnDestroy(): void {
        this.destroy$.next();
        this.destroy$.complete();
    }

    toggleExpanded(): void {
        this.isExpanded = !this.isExpanded;
    }

    hasActiveTransfers(stat: PathPairStat): boolean {
        return stat.downloadingCount > 0 || stat.queuedCount > 0;
    }

    private computeStats(pairs: PathPair[], files: Immutable.List<ViewFile>): PathPairStat[] {
        if (pairs.length === 0) {
            return [];
        }

        const filesByPathPair = new Map<string, ViewFile[]>();
        for (const pair of pairs) {
            filesByPathPair.set(pair.id, []);
        }
        files.forEach(file => {
            if (file.pathPairId) {
                const existing = filesByPathPair.get(file.pathPairId) || [];
                existing.push(file);
                filesByPathPair.set(file.pathPairId, existing);
            }
        });

        return pairs
            .filter(pair => pair.enabled)
            .map(pair => this.calculateStats(pair, filesByPathPair.get(pair.id) || []));
    }

    private calculateStats(pair: PathPair, files: ViewFile[]): PathPairStat {
        let downloadingCount = 0;
        let queuedCount = 0;
        let downloadedCount = 0;
        let totalRemoteSize = 0;
        let totalTransferredSize = 0;
        let totalSpeed = 0;

        for (const file of files) {
            totalRemoteSize += file.remoteSize || 0;

            switch (file.status) {
                case ViewFile.Status.DOWNLOADING:
                    downloadingCount++;
                    totalSpeed += file.downloadingSpeed || 0;
                    totalTransferredSize += Math.min(file.localSize || 0, file.remoteSize || 0);
                    break;
                case ViewFile.Status.QUEUED:
                    queuedCount++;
                    break;
                case ViewFile.Status.DOWNLOADED:
                case ViewFile.Status.EXTRACTING:
                case ViewFile.Status.EXTRACTED:
                case ViewFile.Status.VALIDATING:
                case ViewFile.Status.VALIDATED:
                    downloadedCount++;
                    totalTransferredSize += file.remoteSize || 0;
                    break;
            }
        }

        const overallProgress = totalRemoteSize > 0
            ? Math.min(100, Math.round((totalTransferredSize / totalRemoteSize) * 100))
            : 0;

        return {
            pathPairId: pair.id,
            pathPairName: pair.name,
            remotePath: pair.remote_path,
            localPath: pair.local_path,
            totalFiles: files.length,
            downloadingCount,
            queuedCount,
            downloadedCount,
            totalRemoteSize,
            totalTransferredSize,
            totalSpeed,
            overallProgress
        };
    }
}
