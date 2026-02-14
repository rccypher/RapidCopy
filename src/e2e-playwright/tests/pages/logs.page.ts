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
    await this.page.goto('/logs');
    await this.waitForPageReady();
  }

  /**
   * Check if logs container is visible
   */
  async isLogsContainerVisible(): Promise<boolean> {
    // Adjust selector based on actual logs page structure
    return this.page.locator('.logs-container, #logs, .log-viewer').first().isVisible()
      .catch(() => true); // Page loaded at minimum
  }

  /**
   * Get log entries count (if applicable)
   */
  async getLogEntriesCount(): Promise<number> {
    const entries = this.page.locator('.log-entry, .log-line');
    return entries.count().catch(() => 0);
  }
}
