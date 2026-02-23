import {
    AfterContentChecked,
    ChangeDetectionStrategy, ChangeDetectorRef, Component, ElementRef, HostListener,
    OnDestroy, OnInit, ViewChild, ViewContainerRef
} from "@angular/core";
import {Subject, timer} from "rxjs";
import {takeUntil, debounceTime, distinctUntilChanged, switchMap} from "rxjs/operators";

import {LogService} from "../../services/logs/log.service";
import {LogRecord} from "../../services/logs/log-record";
import {LogQueryService} from "../../services/logs/log-query.service";
import {StreamServiceRegistry} from "../../services/base/stream-service.registry";
import {Localization} from "../../common/localization";
import {DomService} from "../../services/utils/dom.service";
import {Observable} from "rxjs";

@Component({
    selector: "app-logs-page",
    templateUrl: "./logs-page.component.html",
    styleUrls: ["./logs-page.component.scss"],
    providers: [],
    changeDetection: ChangeDetectionStrategy.OnPush
})

export class LogsPageComponent implements OnInit, AfterContentChecked, OnDestroy {
    public readonly LogRecord = LogRecord;
    public readonly Localization = Localization;
    public readonly LEVELS = ["", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"];

    private static readonly MAX_LIVE_RECORDS = 500;

    private static readonly LEVEL_ORDER: Record<string, number> = {
        DEBUG: 0, INFO: 1, WARNING: 2, ERROR: 3, CRITICAL: 4
    };

    public headerHeight: Observable<number>;

    @ViewChild("templateRecord") templateRecord;
    @ViewChild("templateConnected") templateConnected;
    @ViewChild("container", {read: ViewContainerRef}) container;
    @ViewChild("logHead") logHead;
    @ViewChild("logTail") logTail;

    public showScrollToTopButton = false;
    public showScrollToBottomButton = false;

    // Search state
    public searchText = "";
    public levelFilter = "INFO";
    public isSearching = false;
    public searchResults: LogRecord[] = [];
    public searchTruncated = false;
    public searchError = "";

    private _logService: LogService;
    private destroy$ = new Subject<void>();
    private search$ = new Subject<{text: string, level: string}>();

    constructor(private _elementRef: ElementRef,
                private _changeDetector: ChangeDetectorRef,
                private _streamRegistry: StreamServiceRegistry,
                private _domService: DomService,
                private _logQueryService: LogQueryService) {
        this._logService = _streamRegistry.logService;
        this.headerHeight = this._domService.headerHeight;
    }

    get isFiltered(): boolean {
        return this.searchText.trim().length > 0 || (this.levelFilter.length > 0 && this.levelFilter !== "INFO");
    }

    ngOnInit() {
        // Live stream -- shown when no filter is active
        this._logService.logs
            .pipe(takeUntil(this.destroy$))
            .subscribe({
                next: record => {
                    if (!this.isFiltered) {
                        if (!this.passesLevelFilter(record)) { return; }
                        this.insertRecord(record);
                    }
                }
            });

        // Search pipeline -- debounced, cancels previous in-flight request
        this.search$.pipe(
            debounceTime(400),
            distinctUntilChanged((a, b) => a.text === b.text && a.level === b.level),
            switchMap(({text, level}) => {
                if (!text && !level) {
                    return [];
                }
                this.isSearching = true;
                this.searchError = "";
                this._changeDetector.markForCheck();
                return this._logQueryService.search({
                    search: text || undefined,
                    level: level || undefined,
                    limit: 500
                });
            }),
            takeUntil(this.destroy$)
        ).subscribe({
            next: result => {
                this.isSearching = false;
                this.searchResults = result.records;
                this.searchTruncated = result.truncated;
                this._changeDetector.markForCheck();
                timer(50).pipe(takeUntil(this.destroy$)).subscribe(() => this.scrollToBottom());
            },
            error: err => {
                this.isSearching = false;
                this.searchError = "Search unavailable -- log persistence may not be enabled.";
                this._changeDetector.markForCheck();
            }
        });
    }

    ngOnDestroy() {
        this.destroy$.next();
        this.destroy$.complete();
    }

    ngAfterContentChecked() {
        this.refreshScrollButtonVisibility();
    }

    onSearchChange(): void {
        if (!this.isFiltered) {
            this.searchResults = [];
            this.searchTruncated = false;
            this.searchError = "";
            this._changeDetector.markForCheck();
            return;
        }
        this.search$.next({text: this.searchText.trim(), level: this.levelFilter});
    }

    onLevelChange(): void {
        this.onSearchChange();
    }

    clearSearch(): void {
        this.searchText = "";
        this.levelFilter = "INFO";
        this.searchResults = [];
        this.searchTruncated = false;
        this.searchError = "";
        this._changeDetector.markForCheck();
    }

    scrollToTop() {
        window.scrollTo(0, 0);
    }

    scrollToBottom() {
        window.scrollTo(0, document.body.scrollHeight);
    }

    @HostListener("window:scroll", ["$event"])
    checkScroll() {
        this.refreshScrollButtonVisibility();
    }

    getLevelClass(level: LogRecord.Level): string {
        switch (level) {
            case LogRecord.Level.DEBUG:    return "debug";
            case LogRecord.Level.INFO:     return "info";
            case LogRecord.Level.WARNING:  return "warning";
            case LogRecord.Level.ERROR:    return "error";
            case LogRecord.Level.CRITICAL: return "critical";
            default: return "";
        }
    }

    private passesLevelFilter(record: LogRecord): boolean {
        if (!this.levelFilter) { return true; }
        const minOrder = LogsPageComponent.LEVEL_ORDER[this.levelFilter] ?? 0;
        const recOrder = LogsPageComponent.LEVEL_ORDER[record.level as unknown as string] ?? 0;
        return recOrder >= minOrder;
    }

    private insertRecord(record: LogRecord) {
        if (!this.container || !this.templateRecord) {
            return;
        }
        const scrollToBottom = this._elementRef.nativeElement.offsetParent != null &&
            this.logTail && LogsPageComponent.isElementInViewport(this.logTail.nativeElement);
        this.container.createEmbeddedView(this.templateRecord, {record: record});
        // Evict oldest entries to keep the DOM bounded
        while (this.container.length > LogsPageComponent.MAX_LIVE_RECORDS) {
            this.container.remove(0);
        }
        this._changeDetector.detectChanges();
        if (scrollToBottom) {
            this.scrollToBottom();
        }
        this.refreshScrollButtonVisibility();
    }

    private refreshScrollButtonVisibility() {
        if (!this.logHead || !this.logTail) {
            return;
        }
        this.showScrollToTopButton = !LogsPageComponent.isElementInViewport(
            this.logHead.nativeElement
        );
        this.showScrollToBottomButton = !LogsPageComponent.isElementInViewport(
            this.logTail.nativeElement
        );
        this._changeDetector.markForCheck();
    }

    private static isElementInViewport(el): boolean {
        const rect = el.getBoundingClientRect();
        return (
            rect.top >= 0 &&
            rect.left >= 0 &&
            rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
            rect.right <= (window.innerWidth || document.documentElement.clientWidth)
        );
    }
}
