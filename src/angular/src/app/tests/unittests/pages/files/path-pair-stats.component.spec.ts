import {ComponentFixture, TestBed, fakeAsync, tick} from "@angular/core/testing";
import {ChangeDetectorRef} from "@angular/core";
import {BehaviorSubject, Subject} from "rxjs";

import * as Immutable from "immutable";

import {PathPairStatsComponent, PathPairStat} from "../../../../pages/files/path-pair-stats.component";
import {ViewFile} from "../../../../services/files/view-file";
import {ViewFileService} from "../../../../services/files/view-file.service";
import {PathPairService, PathPair} from "../../../../services/settings/path-pair.service";


/**
 * Mock ViewFileService for testing
 */
class MockViewFileService {
    private _files = new BehaviorSubject<Immutable.List<ViewFile>>(Immutable.List());

    get files() {
        return this._files.asObservable();
    }

    setFiles(files: ViewFile[]) {
        this._files.next(Immutable.List(files));
    }
}

/**
 * Mock PathPairService for testing
 */
class MockPathPairService {
    private _pathPairs$ = new BehaviorSubject<PathPair[]>([]);

    get pathPairs$() {
        return this._pathPairs$.asObservable();
    }

    setPathPairs(pairs: PathPair[]) {
        this._pathPairs$.next(pairs);
    }
}

/**
 * Helper to create a ViewFile with specified properties
 */
function createViewFile(props: Partial<{
    name: string;
    status: ViewFile.Status;
    remoteSize: number;
    localSize: number;
    downloadingSpeed: number;
    pathPairId: string;
    pathPairName: string;
}>): ViewFile {
    return new ViewFile({
        name: props.name || "test-file.txt",
        isDir: false,
        localSize: props.localSize ?? 0,
        remoteSize: props.remoteSize ?? 1000,
        percentDownloaded: props.localSize && props.remoteSize ? (props.localSize / props.remoteSize) * 100 : 0,
        status: props.status || ViewFile.Status.DEFAULT,
        downloadingSpeed: props.downloadingSpeed ?? 0,
        eta: 0,
        fullPath: `/path/${props.name || "test-file.txt"}`,
        isArchive: false,
        isSelected: false,
        isQueueable: true,
        isStoppable: false,
        isExtractable: false,
        isLocallyDeletable: true,
        isRemotelyDeletable: true,
        isValidatable: false,
        localCreatedTimestamp: null,
        localModifiedTimestamp: null,
        remoteCreatedTimestamp: null,
        remoteModifiedTimestamp: null,
        pathPairId: props.pathPairId || null,
        pathPairName: props.pathPairName || null,
        validationProgress: null,
        validationError: null,
        corruptChunks: null
    });
}

/**
 * Helper to create a PathPair
 */
function createPathPair(id: string, name: string, enabled = true): PathPair {
    return {
        id,
        name,
        remote_path: `/remote/${name.toLowerCase()}`,
        local_path: `/local/${name.toLowerCase()}`,
        enabled,
        auto_queue: true
    };
}


describe("PathPairStatsComponent", () => {
    let component: PathPairStatsComponent;
    let fixture: ComponentFixture<PathPairStatsComponent>;
    let mockViewFileService: MockViewFileService;
    let mockPathPairService: MockPathPairService;

    beforeEach(async () => {
        mockViewFileService = new MockViewFileService();
        mockPathPairService = new MockPathPairService();

        await TestBed.configureTestingModule({
            imports: [PathPairStatsComponent],
            providers: [
                {provide: ViewFileService, useValue: mockViewFileService},
                {provide: PathPairService, useValue: mockPathPairService}
            ]
        }).compileComponents();

        fixture = TestBed.createComponent(PathPairStatsComponent);
        component = fixture.componentInstance;
    });

    afterEach(() => {
        fixture.destroy();
    });

    describe("Initialization", () => {
        it("should create the component", () => {
            expect(component).toBeTruthy();
        });

        it("should start with empty stats", () => {
            fixture.detectChanges();
            expect(component.stats).toEqual([]);
        });

        it("should start expanded", () => {
            fixture.detectChanges();
            expect(component.isExpanded).toBe(true);
        });

        it("should not have multiple path pairs initially", () => {
            fixture.detectChanges();
            expect(component.hasMultiplePathPairs).toBe(false);
        });
    });

    describe("Path pair detection", () => {
        it("should detect single path pair", fakeAsync(() => {
            mockPathPairService.setPathPairs([
                createPathPair("pair-1", "Movies")
            ]);
            fixture.detectChanges();
            tick();

            expect(component.hasMultiplePathPairs).toBe(false);
        }));

        it("should detect multiple path pairs", fakeAsync(() => {
            mockPathPairService.setPathPairs([
                createPathPair("pair-1", "Movies"),
                createPathPair("pair-2", "TV Shows")
            ]);
            fixture.detectChanges();
            tick();

            expect(component.hasMultiplePathPairs).toBe(true);
        }));

        it("should update when path pairs change", fakeAsync(() => {
            mockPathPairService.setPathPairs([
                createPathPair("pair-1", "Movies")
            ]);
            fixture.detectChanges();
            tick();

            expect(component.hasMultiplePathPairs).toBe(false);

            mockPathPairService.setPathPairs([
                createPathPair("pair-1", "Movies"),
                createPathPair("pair-2", "TV Shows")
            ]);
            tick();

            expect(component.hasMultiplePathPairs).toBe(true);
        }));
    });

    describe("Stats calculation", () => {
        beforeEach(fakeAsync(() => {
            mockPathPairService.setPathPairs([
                createPathPair("pair-1", "Movies"),
                createPathPair("pair-2", "TV Shows")
            ]);
            fixture.detectChanges();
            tick();
        }));

        it("should calculate stats for each path pair", fakeAsync(() => {
            mockViewFileService.setFiles([
                createViewFile({name: "movie1.mkv", pathPairId: "pair-1", remoteSize: 1000, localSize: 500}),
                createViewFile({name: "movie2.mkv", pathPairId: "pair-1", remoteSize: 2000, localSize: 2000}),
                createViewFile({name: "show1.mkv", pathPairId: "pair-2", remoteSize: 500, localSize: 250})
            ]);
            tick();

            expect(component.stats.length).toBe(2);
            
            const movieStats = component.stats.find(s => s.pathPairId === "pair-1");
            expect(movieStats).toBeTruthy();
            expect(movieStats!.totalFiles).toBe(2);
            expect(movieStats!.totalRemoteSize).toBe(3000);
            expect(movieStats!.totalLocalSize).toBe(2500);

            const tvStats = component.stats.find(s => s.pathPairId === "pair-2");
            expect(tvStats).toBeTruthy();
            expect(tvStats!.totalFiles).toBe(1);
            expect(tvStats!.totalRemoteSize).toBe(500);
            expect(tvStats!.totalLocalSize).toBe(250);
        }));

        it("should count downloading files", fakeAsync(() => {
            mockViewFileService.setFiles([
                createViewFile({
                    name: "downloading.mkv",
                    pathPairId: "pair-1",
                    status: ViewFile.Status.DOWNLOADING,
                    downloadingSpeed: 1000000
                }),
                createViewFile({
                    name: "another.mkv",
                    pathPairId: "pair-1",
                    status: ViewFile.Status.DOWNLOADING,
                    downloadingSpeed: 500000
                })
            ]);
            tick();

            const stats = component.stats.find(s => s.pathPairId === "pair-1");
            expect(stats!.downloadingCount).toBe(2);
            expect(stats!.totalSpeed).toBe(1500000);
        }));

        it("should count queued files", fakeAsync(() => {
            mockViewFileService.setFiles([
                createViewFile({name: "queued1.mkv", pathPairId: "pair-1", status: ViewFile.Status.QUEUED}),
                createViewFile({name: "queued2.mkv", pathPairId: "pair-1", status: ViewFile.Status.QUEUED}),
                createViewFile({name: "queued3.mkv", pathPairId: "pair-1", status: ViewFile.Status.QUEUED})
            ]);
            tick();

            const stats = component.stats.find(s => s.pathPairId === "pair-1");
            expect(stats!.queuedCount).toBe(3);
        }));

        it("should count downloaded files including extracted and validated", fakeAsync(() => {
            mockViewFileService.setFiles([
                createViewFile({name: "downloaded.mkv", pathPairId: "pair-1", status: ViewFile.Status.DOWNLOADED}),
                createViewFile({name: "extracted.mkv", pathPairId: "pair-1", status: ViewFile.Status.EXTRACTED}),
                createViewFile({name: "validated.mkv", pathPairId: "pair-1", status: ViewFile.Status.VALIDATED})
            ]);
            tick();

            const stats = component.stats.find(s => s.pathPairId === "pair-1");
            expect(stats!.downloadedCount).toBe(3);
        }));

        it("should calculate overall progress percentage", fakeAsync(() => {
            mockViewFileService.setFiles([
                createViewFile({name: "file1.mkv", pathPairId: "pair-1", remoteSize: 1000, localSize: 250}),
                createViewFile({name: "file2.mkv", pathPairId: "pair-1", remoteSize: 1000, localSize: 750})
            ]);
            tick();

            const stats = component.stats.find(s => s.pathPairId === "pair-1");
            // (250 + 750) / (1000 + 1000) = 1000 / 2000 = 50%
            expect(stats!.overallProgress).toBe(50);
        }));

        it("should handle zero remote size gracefully", fakeAsync(() => {
            mockViewFileService.setFiles([
                createViewFile({name: "empty.txt", pathPairId: "pair-1", remoteSize: 0, localSize: 0})
            ]);
            tick();

            const stats = component.stats.find(s => s.pathPairId === "pair-1");
            expect(stats!.overallProgress).toBe(0);
        }));

        it("should only include enabled path pairs in stats", fakeAsync(() => {
            mockPathPairService.setPathPairs([
                createPathPair("pair-1", "Movies", true),
                createPathPair("pair-2", "TV Shows", false)  // disabled
            ]);
            tick();

            mockViewFileService.setFiles([
                createViewFile({name: "movie.mkv", pathPairId: "pair-1"}),
                createViewFile({name: "show.mkv", pathPairId: "pair-2"})
            ]);
            tick();

            // Only the enabled path pair should have stats
            expect(component.stats.length).toBe(1);
            expect(component.stats[0].pathPairId).toBe("pair-1");
        }));
    });

    describe("hasActiveTransfers", () => {
        it("should return true when downloading count > 0", () => {
            const stat: PathPairStat = {
                pathPairId: "pair-1",
                pathPairName: "Movies",
                remotePath: "/remote",
                localPath: "/local",
                totalFiles: 5,
                downloadingCount: 2,
                queuedCount: 0,
                downloadedCount: 3,
                totalRemoteSize: 1000,
                totalLocalSize: 500,
                totalSpeed: 100000,
                overallProgress: 50
            };

            expect(component.hasActiveTransfers(stat)).toBe(true);
        });

        it("should return true when queued count > 0", () => {
            const stat: PathPairStat = {
                pathPairId: "pair-1",
                pathPairName: "Movies",
                remotePath: "/remote",
                localPath: "/local",
                totalFiles: 5,
                downloadingCount: 0,
                queuedCount: 3,
                downloadedCount: 2,
                totalRemoteSize: 1000,
                totalLocalSize: 500,
                totalSpeed: 0,
                overallProgress: 50
            };

            expect(component.hasActiveTransfers(stat)).toBe(true);
        });

        it("should return false when no active transfers", () => {
            const stat: PathPairStat = {
                pathPairId: "pair-1",
                pathPairName: "Movies",
                remotePath: "/remote",
                localPath: "/local",
                totalFiles: 5,
                downloadingCount: 0,
                queuedCount: 0,
                downloadedCount: 5,
                totalRemoteSize: 1000,
                totalLocalSize: 1000,
                totalSpeed: 0,
                overallProgress: 100
            };

            expect(component.hasActiveTransfers(stat)).toBe(false);
        });
    });

    describe("toggleExpanded", () => {
        it("should toggle isExpanded from true to false", () => {
            fixture.detectChanges();
            expect(component.isExpanded).toBe(true);

            component.toggleExpanded();

            expect(component.isExpanded).toBe(false);
        });

        it("should toggle isExpanded from false to true", () => {
            fixture.detectChanges();
            component.isExpanded = false;

            component.toggleExpanded();

            expect(component.isExpanded).toBe(true);
        });
    });

    describe("Cleanup", () => {
        it("should unsubscribe on destroy", fakeAsync(() => {
            mockPathPairService.setPathPairs([
                createPathPair("pair-1", "Movies"),
                createPathPair("pair-2", "TV Shows")
            ]);
            fixture.detectChanges();
            tick();

            // Trigger ngOnDestroy
            component.ngOnDestroy();

            // Updates after destroy should not affect component
            mockPathPairService.setPathPairs([
                createPathPair("pair-3", "Music")
            ]);
            tick();

            // Component should still have old data (not updated)
            expect(component.hasMultiplePathPairs).toBe(true);
        }));
    });

    describe("Files without pathPairId", () => {
        it("should ignore files without pathPairId", fakeAsync(() => {
            mockPathPairService.setPathPairs([
                createPathPair("pair-1", "Movies")
            ]);
            fixture.detectChanges();
            tick();

            mockViewFileService.setFiles([
                createViewFile({name: "with-pair.mkv", pathPairId: "pair-1", remoteSize: 1000}),
                createViewFile({name: "no-pair.mkv", pathPairId: null, remoteSize: 500})
            ]);
            tick();

            const stats = component.stats.find(s => s.pathPairId === "pair-1");
            expect(stats!.totalFiles).toBe(1);
            expect(stats!.totalRemoteSize).toBe(1000);
        }));
    });
});
