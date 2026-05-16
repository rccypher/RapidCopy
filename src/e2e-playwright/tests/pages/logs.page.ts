import { Page } from '@playwright/test';
import { BasePage } from '../fixtures';

/**
 * Logs page object
 */
export class LogsPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  /**
   * Navigate to the logs page
   */
  async goto(): Promise<void> {
    // Use domcontentloaded to avoid waiting for WebSocket to complete
    await this.page.goto('/logs', { waitUntil: 'domcontentloaded' });
    await this.waitForPageReady();
  }

  /**
   * Check if logs container is present
   */
  async isLogListPresent(): Promise<boolean> {
    // The logs container is #logs
    return this.page.locator('#logs').isVisible().catch(() => false);
  }

  /**
   * Check if logs container is visible (alias for isLogListPresent)
   */
  async isLogsContainerVisible(): Promise<boolean> {
    return this.isLogListPresent();
  }

  /**
   * Get log entries count
   */
  async getLogEntryCount(): Promise<number> {
    // Log entries have class .record
    return this.page.locator('#logs .record').count().catch(() => 0);
  }

  /**
   * Get log entries count (alias for getLogEntryCount)
   */
  async getLogEntriesCount(): Promise<number> {
    return this.getLogEntryCount();
  }

  /**
   * Get all log entries text
   */
  async getLogEntries(): Promise<string[]> {
    return this.page.locator('#logs .record').allInnerTexts().catch(() => []);
  }

  /**
   * Check if scroll to top button is visible
   */
  async isScrollToTopButtonVisible(): Promise<boolean> {
    return this.page.locator('#btn-scroll-top.visible').isVisible().catch(() => false);
  }

  /**
   * Check if scroll to bottom button is visible
   */
  async isScrollToBottomButtonVisible(): Promise<boolean> {
    return this.page.locator('#btn-scroll-bottom.visible').isVisible().catch(() => false);
  }
}
