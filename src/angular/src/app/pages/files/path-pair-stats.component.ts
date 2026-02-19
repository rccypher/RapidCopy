import {Component, ChangeDetectionStrategy, ChangeDetectorRef, OnInit, OnDestroy} from "@angular/core";
import {CommonModule} from "@angular/common";
import {Subject} from "rxjs";
import {takeUntil} from "rxjs/operators";

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
 * Shows aggregate stats like file counts, speeds, and progress for each path pair.
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
    stats: PathPairStat[] = [];
    isExpanded = true;
    hasMultiplePathPairs = false;

    private destroy$ = new Subject<void>();
    private pathPairs: PathPair[] = [];
    private files: Immutable.List<ViewFile> = Immutable.List();

    constructor(
        private viewFileService: ViewFileService,
        private pathPairService: PathPairService,
        private changeDetector: ChangeDetectorRef
    ) {}

    ngOnInit(): void {
        // Subscribe to path pairs
        this.pathPairService.pathPairs$
            .pipe(takeUntil(this.destroy$))
            .subscribe(pairs => {
                this.pathPairs = pairs;
                this.hasMultiplePathPairs = pairs.length > 1;
                this.updateStats();
            });

        // Subscribe to files
        this.viewFileService.files
            .pipe(takeUntil(this.destroy$))
            .subscribe(files => {
                this.files = files;
                this.updateStats();
            });
    }

    ngOnDestroy(): void {
        this.destroy$.next();
        this.destroy$.complete();
    }

    toggleExpanded(): void {
        this.isExpanded = !this.isExpanded;
    }

    private updateStats(): void {
        if (this.pathPairs.length === 0) {
            this.stats = [];
            this.changeDetector.markForCheck();
            return;
        }

        // Group files by path pair ID
        const filesByPathPair = new Map<string, ViewFile[]>();
        
        // Initialize with all known path pairs
        for (const pair of this.pathPairs) {
            filesByPathPair.set(pair.id, []);
        }

        // Group files
        this.files.forEach(file => {
            if (file.pathPairId) {
                const existing = filesByPathPair.get(file.pathPairId) || [];
                existing.push(file);
                filesByPathPair.set(file.pathPairId, existing);
            }
        });

        // Calculate stats for each path pair
        this.stats = this.pathPairs
            .filter(pair => pair.enabled)
            .map(pair => {
                const pairFiles = filesByPathPair.get(pair.id) || [];
                return this.calculateStats(pair, pairFiles);
            });

        this.changeDetector.markForCheck();
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
                    // Count bytes actually on disk for in-progress files (capped at remoteSize)
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
                    // Count the remote size (the actual amount transferred) not local disk size
                    // (local disk may be larger after extraction, or smaller if file was deleted)
                    totalTransferredSize += file.remoteSize || 0;
                    break;
            }
        }

        // Progress = transferred bytes / total remote bytes, capped at 100%
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

    // Helper to determine if a path pair has active transfers
    hasActiveTransfers(stat: PathPairStat): boolean {
        return stat.downloadingCount > 0 || stat.queuedCount > 0;
    }
}
