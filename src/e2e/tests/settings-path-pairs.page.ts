import {browser, by, element, ExpectedConditions} from 'protractor';
import {promise} from "selenium-webdriver";
import Promise = promise.Promise;

import {Urls} from "../urls";
import {App} from "./app";

/**
 * Represents a path pair as displayed in the settings page
 */
export class PathPairItem {
    constructor(
        public name: string,
        public remotePath: string,
        public localPath: string,
        public isEnabled: boolean,
        public hasAutoQueue: boolean
    ) {}
}

/**
 * Page object for settings page with path pairs functionality
 */
export class SettingsPathPairsPage extends App {
    navigateTo() {
        return browser.get(Urls.APP_BASE_URL + "settings").then(() => {
            // Wait for the path pairs container to be present
            return browser.wait(ExpectedConditions.presenceOf(
                element(by.css(".path-pairs-container"))
            ), 5000);
        });
    }

    /**
     * Get the header title of the path pairs section
     */
    getPathPairsSectionTitle(): Promise<string> {
        return element(by.css(".path-pairs-container .header h4")).getText();
    }

    /**
     * Get all path pair items displayed
     */
    getPathPairs(): Promise<Array<PathPairItem>> {
        return element.all(by.css(".path-pairs-container .path-pair-item")).map(elm => {
            const name = elm.element(by.css(".pair-name")).getText();
            const remotePath = elm.element(by.css(".path-row:first-child .path-value")).getText();
            const localPath = elm.element(by.css(".path-row:last-child .path-value")).getText();
            const isEnabled = elm.element(by.css(".pair-status.enabled")).isPresent();
            const hasAutoQueue = elm.element(by.css(".auto-queue-badge")).isPresent();
            return new PathPairItem(name, remotePath, localPath, isEnabled, hasAutoQueue);
        });
    }

    /**
     * Get count of path pairs
     */
    getPathPairCount(): Promise<number> {
        return element.all(by.css(".path-pairs-container .path-pair-item")).count();
    }

    /**
     * Check if the Add Path Pair button is present
     */
    isAddButtonPresent(): Promise<boolean> {
        return element(by.css(".path-pairs-container .add-btn")).isPresent();
    }

    /**
     * Click the Add Path Pair button
     */
    clickAddButton() {
        return element(by.css(".path-pairs-container .add-btn")).click();
    }

    /**
     * Check if the create/edit form is displayed
     */
    isFormDisplayed(): Promise<boolean> {
        return element(by.css(".path-pairs-container .form-card")).isDisplayed();
    }

    /**
     * Get the form title (New Path Pair or Edit Path Pair)
     */
    getFormTitle(): Promise<string> {
        return element(by.css(".path-pairs-container .form-card h5")).getText();
    }

    /**
     * Fill in the path pair form
     */
    fillForm(name: string, remotePath: string, localPath: string) {
        const nameInput = element(by.css(".path-pairs-container #name"));
        const remotePathInput = element(by.css(".path-pairs-container #remotePath"));
        const localPathInput = element(by.css(".path-pairs-container #localPath"));

        nameInput.clear();
        nameInput.sendKeys(name);
        remotePathInput.clear();
        remotePathInput.sendKeys(remotePath);
        localPathInput.clear();
        localPathInput.sendKeys(localPath);
    }

    /**
     * Click Save button on the form
     */
    clickSave() {
        return element(by.css(".path-pairs-container .form-card .btn-primary")).click();
    }

    /**
     * Click Cancel button on the form
     */
    clickCancel() {
        return element(by.css(".path-pairs-container .form-card .btn-secondary")).click();
    }

    /**
     * Click Edit button on a specific path pair
     */
    clickEditButton(index: number) {
        return element.all(by.css(".path-pairs-container .path-pair-item"))
            .get(index)
            .element(by.css(".btn-edit"))
            .click();
    }

    /**
     * Click Delete button on a specific path pair
     */
    clickDeleteButton(index: number) {
        return element.all(by.css(".path-pairs-container .path-pair-item"))
            .get(index)
            .element(by.css(".btn-danger"))
            .click();
    }

    /**
     * Click Toggle (Enable/Disable) button on a specific path pair
     */
    clickToggleButton(index: number) {
        return element.all(by.css(".path-pairs-container .path-pair-item"))
            .get(index)
            .element(by.css(".btn-toggle"))
            .click();
    }

    /**
     * Check if the empty state message is displayed
     */
    isEmptyStateDisplayed(): Promise<boolean> {
        return element(by.css(".path-pairs-container .empty-state")).isPresent();
    }

    /**
     * Get the empty state message text
     */
    getEmptyStateText(): Promise<string> {
        return element(by.css(".path-pairs-container .empty-state p")).getText();
    }
}
