import {fakeAsync, TestBed, tick} from "@angular/core/testing";

import {ThemeService, Theme} from "../../../../services/utils/theme.service";
import {LoggerService} from "../../../../services/utils/logger.service";
import {MockStorageService} from "../../../mocks/mock-storage.service";
import {LOCAL_STORAGE} from "ngx-webstorage-service";
import {StorageKeys} from "../../../../common/storage-keys";


describe("Testing theme service", () => {
    let themeService: ThemeService;
    let storageService: MockStorageService;
    let originalMatchMedia: typeof window.matchMedia;

    // Helper to mock matchMedia for system preference detection
    function mockMatchMedia(prefersDark: boolean): void {
        window.matchMedia = jasmine.createSpy('matchMedia').and.callFake((query: string) => ({
            matches: query === '(prefers-color-scheme: dark)' ? prefersDark : false,
            media: query,
            onchange: null,
            addListener: jasmine.createSpy('addListener'),
            removeListener: jasmine.createSpy('removeListener'),
            addEventListener: jasmine.createSpy('addEventListener'),
            removeEventListener: jasmine.createSpy('removeEventListener'),
            dispatchEvent: jasmine.createSpy('dispatchEvent'),
        } as MediaQueryList));
    }

    beforeEach(() => {
        // Save original matchMedia
        originalMatchMedia = window.matchMedia;

        // Default to light system preference
        mockMatchMedia(false);

        TestBed.configureTestingModule({
            providers: [
                LoggerService,
                ThemeService,
                {provide: LOCAL_STORAGE, useClass: MockStorageService},
            ]
        });

        storageService = TestBed.inject(LOCAL_STORAGE) as MockStorageService;
    });

    afterEach(() => {
        // Restore original matchMedia
        window.matchMedia = originalMatchMedia;
        // Clean up document attribute
        document.documentElement.removeAttribute('data-theme');
    });

    function createService(): ThemeService {
        return TestBed.inject(ThemeService);
    }

    it("should create an instance", () => {
        themeService = createService();
        expect(themeService).toBeDefined();
    });

    describe("Initial theme loading", () => {

        it("should load 'light' theme from storage if stored", () => {
            storageService.set(StorageKeys.THEME_PREFERENCE, 'light');
            themeService = createService();

            expect(themeService.currentTheme).toBe('light');
            expect(document.documentElement.getAttribute('data-theme')).toBe('light');
        });

        it("should load 'dark' theme from storage if stored", () => {
            storageService.set(StorageKeys.THEME_PREFERENCE, 'dark');
            themeService = createService();

            expect(themeService.currentTheme).toBe('dark');
            expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
        });

        it("should detect system dark preference when no stored theme", () => {
            mockMatchMedia(true);  // System prefers dark
            themeService = createService();

            expect(themeService.currentTheme).toBe('dark');
            expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
        });

        it("should detect system light preference when no stored theme", () => {
            mockMatchMedia(false);  // System prefers light
            themeService = createService();

            expect(themeService.currentTheme).toBe('light');
            expect(document.documentElement.getAttribute('data-theme')).toBe('light');
        });

        it("should ignore invalid stored theme and use system preference", () => {
            storageService.set(StorageKeys.THEME_PREFERENCE, 'invalid-theme');
            mockMatchMedia(true);  // System prefers dark
            themeService = createService();

            expect(themeService.currentTheme).toBe('dark');
        });
    });

    describe("Theme observable", () => {

        it("should emit current theme on subscription", fakeAsync(() => {
            storageService.set(StorageKeys.THEME_PREFERENCE, 'dark');
            themeService = createService();

            let emittedTheme: Theme | undefined;
            themeService.theme$.subscribe(theme => {
                emittedTheme = theme;
            });
            tick();

            expect(emittedTheme).toBe('dark');
        }));

        it("should emit when theme changes", fakeAsync(() => {
            themeService = createService();

            const emittedThemes: Theme[] = [];
            themeService.theme$.subscribe(theme => {
                emittedThemes.push(theme);
            });
            tick();

            themeService.setTheme('dark');
            tick();

            themeService.setTheme('light');
            tick();

            expect(emittedThemes).toEqual(['light', 'dark', 'light']);
        }));
    });

    describe("setTheme", () => {

        it("should set theme to dark", () => {
            themeService = createService();

            themeService.setTheme('dark');

            expect(themeService.currentTheme).toBe('dark');
            expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
        });

        it("should set theme to light", () => {
            storageService.set(StorageKeys.THEME_PREFERENCE, 'dark');
            themeService = createService();

            themeService.setTheme('light');

            expect(themeService.currentTheme).toBe('light');
            expect(document.documentElement.getAttribute('data-theme')).toBe('light');
        });

        it("should persist theme to storage", () => {
            themeService = createService();

            themeService.setTheme('dark');

            expect(storageService.get(StorageKeys.THEME_PREFERENCE)).toBe('dark');
        });

        it("should not emit if setting same theme", fakeAsync(() => {
            storageService.set(StorageKeys.THEME_PREFERENCE, 'dark');
            themeService = createService();

            const emittedThemes: Theme[] = [];
            themeService.theme$.subscribe(theme => {
                emittedThemes.push(theme);
            });
            tick();

            themeService.setTheme('dark');  // Same theme
            tick();

            expect(emittedThemes).toEqual(['dark']);
        }));
    });

    describe("toggleTheme", () => {

        it("should toggle from light to dark", () => {
            themeService = createService();
            expect(themeService.currentTheme).toBe('light');

            themeService.toggleTheme();

            expect(themeService.currentTheme).toBe('dark');
            expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
        });

        it("should toggle from dark to light", () => {
            storageService.set(StorageKeys.THEME_PREFERENCE, 'dark');
            themeService = createService();
            expect(themeService.currentTheme).toBe('dark');

            themeService.toggleTheme();

            expect(themeService.currentTheme).toBe('light');
            expect(document.documentElement.getAttribute('data-theme')).toBe('light');
        });

        it("should persist toggled theme to storage", () => {
            themeService = createService();

            themeService.toggleTheme();

            expect(storageService.get(StorageKeys.THEME_PREFERENCE)).toBe('dark');

            themeService.toggleTheme();

            expect(storageService.get(StorageKeys.THEME_PREFERENCE)).toBe('light');
        });

        it("should emit theme changes on toggle", fakeAsync(() => {
            themeService = createService();

            const emittedThemes: Theme[] = [];
            themeService.theme$.subscribe(theme => {
                emittedThemes.push(theme);
            });
            tick();

            themeService.toggleTheme();
            tick();
            themeService.toggleTheme();
            tick();

            expect(emittedThemes).toEqual(['light', 'dark', 'light']);
        }));
    });

    describe("isDarkMode", () => {

        it("should return false when theme is light", () => {
            themeService = createService();

            expect(themeService.isDarkMode).toBe(false);
        });

        it("should return true when theme is dark", () => {
            storageService.set(StorageKeys.THEME_PREFERENCE, 'dark');
            themeService = createService();

            expect(themeService.isDarkMode).toBe(true);
        });

        it("should update after theme change", () => {
            themeService = createService();
            expect(themeService.isDarkMode).toBe(false);

            themeService.setTheme('dark');
            expect(themeService.isDarkMode).toBe(true);

            themeService.setTheme('light');
            expect(themeService.isDarkMode).toBe(false);
        });
    });

    describe("DOM attribute application", () => {

        it("should set data-theme attribute on document element", () => {
            themeService = createService();

            expect(document.documentElement.getAttribute('data-theme')).toBe('light');

            themeService.setTheme('dark');

            expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
        });

        it("should apply theme on initialization", () => {
            storageService.set(StorageKeys.THEME_PREFERENCE, 'dark');

            themeService = createService();

            expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
        });
    });
});
