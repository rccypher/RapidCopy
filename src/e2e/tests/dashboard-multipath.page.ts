import {browser, by, element, ExpectedConditions} from 'protractor';
import {promise} from "selenium-webdriver";
import Promise = promise.Promise;

import {Urls} from "../urls";
import {App} from "./app";

/**
 * Represents a path pair stat card on the dashboard
 */
export class PathPairStatCard {
    constructor(
        public name: string,
        public fileCount: string,
        public progress: number,
        public downloadingCount: number,
        public queuedCount: number,
        public downloadedCount: number
    ) {}
}

/**
 * Represents a file with path pair information
 */
export class FileWithPathPair {
    constructor(
        public name: string,
        public pathPairName: string | null
    ) {}
}

/**
 * Page object for dashboard with multi-path features
 */
export class DashboardMultiPathPage extends App {
    navigateTo() {
        return browser.get(Urls.APP_BASE_URL + "dashboard").then(() => {
            // Wait for the files list to show up
            return browser.wait(ExpectedConditions.presenceOf(
                element.all(by.css("#file-list .file")).first()
            ), 5000);
        });
    }

    /**
     * Check if the path pair stats container is present
     */
    isPathPairStatsPresent(): Promise<boolean> {
        return element(by.css(".path-pair-stats-container")).isPresent();
    }

    /**
     * Check if the path pair stats is expanded
     */
    isPathPairStatsExpanded(): Promise<boolean> {
        return element(by.css(".path-pair-stats-container .stats-grid")).isDisplayed();
    }

    /**
     * Get the path pair stats header title
     */
    getPathPairStatsTitle(): Promise<string> {
        return element(by.css(".path-pair-stats-container .header .title span")).getText();
    }

    /**
     * Toggle the path pair stats expansion
     */
    togglePathPairStats() {
        return element(by.css(".path-pair-stats-container .header")).click();
    }

    /**
     * Get all path pair stat cards
     */
    getPathPairStatCards(): Promise<Array<PathPairStatCard>> {
        return element.all(by.css(".path-pair-stats-container .path-pair-card")).map(elm => {
            const name = elm.element(by.css(".pair-name")).getText();
            const fileCount = elm.element(by.css(".file-count")).getText();
            
            // Get progress percentage from width style
            const progress = elm.element(by.css(".progress-bar")).getCssValue("width").then(width => {
                // Parse percentage from width
                return parseInt(width) || 0;
            });
            
            // Count stat items (they may not all be present)
            const downloadingCount = elm.all(by.css(".stat")).filter(stat => {
                return stat.element(by.css(".stat-label")).getText().then(text => text === "downloading");
            }).count().then(count => count > 0 ? 1 : 0);
            
            const queuedCount = elm.all(by.css(".stat")).filter(stat => {
                return stat.element(by.css(".stat-label")).getText().then(text => text === "queued");
            }).count().then(count => count > 0 ? 1 : 0);
            
            const downloadedCount = elm.all(by.css(".stat")).filter(stat => {
                return stat.element(by.css(".stat-label")).getText().then(text => text === "done");
            }).count().then(count => count > 0 ? 1 : 0);
            
            return new PathPairStatCard(name, fileCount, progress, downloadingCount, queuedCount, downloadedCount);
        });
    }

    /**
     * Get count of path pair stat cards
     */
    getPathPairStatCardCount(): Promise<number> {
        return element.all(by.css(".path-pair-stats-container .path-pair-card")).count();
    }

    /**
     * Get files with their path pair badges
     */
    getFilesWithPathPairs(): Promise<Array<FileWithPathPair>> {
        return element.all(by.css("#file-list .file")).map(elm => {
            const name = elm.element(by.css(".name .text .title")).getText().then(text => {
                // Remove the badge text if present
                return text.split("\n")[0].trim();
            });
            
            const pathPairName = elm.element(by.css(".path-pair-badge")).isPresent().then(present => {
                if (present) {
                    return elm.element(by.css(".path-pair-badge")).getText();
                }
                return null;
            });
            
            return new FileWithPathPair(name, pathPairName);
        });
    }

    /**
     * Check if any file has a path pair badge
     */
    hasAnyPathPairBadge(): Promise<boolean> {
        return element.all(by.css("#file-list .file .path-pair-badge")).count().then(count => count > 0);
    }

    /**
     * Get all unique path pair names from file badges
     */
    getUniquePathPairNames(): Promise<Array<string>> {
        return element.all(by.css("#file-list .file .path-pair-badge")).map(elm => {
            return elm.getText();
        }).then((names: string[]) => {
            return [...new Set(names)];
        });
    }
}
