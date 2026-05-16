import { Injectable, Inject } from '@angular/core';
import { LOCAL_STORAGE, StorageService } from 'ngx-webstorage-service';
import { BehaviorSubject, Observable } from 'rxjs';

import { LoggerService } from './logger.service';
import { StorageKeys } from '../../common/storage-keys';

export type Theme = 'light' | 'dark';

/**
 * ThemeService provides theme management services for the application.
 *
 * Features:
 * - Persists theme preference to localStorage
 * - Detects system preference on first load
 * - Provides observable for theme changes
 * - Applies theme via data-theme attribute on document root
 */
@Injectable({ providedIn: 'root' })
export class ThemeService {
    private _theme: BehaviorSubject<Theme>;

    constructor(
        private _logger: LoggerService,
        @Inject(LOCAL_STORAGE) private _storage: StorageService
    ) {
        const initialTheme = this.loadTheme();
        this._theme = new BehaviorSubject<Theme>(initialTheme);
        this.applyTheme(initialTheme);
    }

    /**
     * Observable of the current theme
     */
    get theme$(): Observable<Theme> {
        return this._theme.asObservable();
    }

    /**
     * Get the current theme value
     */
    get currentTheme(): Theme {
        return this._theme.getValue();
    }

    /**
     * Check if dark mode is active
     */
    get isDarkMode(): boolean {
        return this._theme.getValue() === 'dark';
    }

    /**
     * Set the theme and persist to storage
     */
    setTheme(theme: Theme): void {
        if (this._theme.getValue() !== theme) {
            this.applyTheme(theme);
            this._storage.set(StorageKeys.THEME_PREFERENCE, theme);
            this._theme.next(theme);
            this._logger.debug(`Theme set to: ${theme}`);
        }
    }

    /**
     * Toggle between light and dark themes
     */
    toggleTheme(): void {
        const newTheme: Theme = this._theme.getValue() === 'light' ? 'dark' : 'light';
        this.setTheme(newTheme);
    }

    /**
     * Load theme from storage or detect system preference
     */
    private loadTheme(): Theme {
        const stored = this._storage.get(StorageKeys.THEME_PREFERENCE);
        if (stored === 'light' || stored === 'dark') {
            return stored;
        }
        return this.getSystemPreference();
    }

    /**
     * Detect system color scheme preference
     */
    private getSystemPreference(): Theme {
        if (typeof window !== 'undefined' && window.matchMedia) {
            return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        }
        return 'light';
    }

    /**
     * Apply theme to document root element
     */
    private applyTheme(theme: Theme): void {
        if (typeof document !== 'undefined') {
            document.documentElement.setAttribute('data-theme', theme);
        }
    }
}
