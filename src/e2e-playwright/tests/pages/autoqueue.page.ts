import { Page } from '@playwright/test';
import { BasePage } from '../fixtures';

/**
 * AutoQueue page object
 */
export class AutoQueuePage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  /**
   * Navigate to the autoqueue page
   */
  async goto(): Promise<void> {
    // Use domcontentloaded to avoid waiting for WebSocket to complete
    await this.page.goto('/autoqueue', { waitUntil: 'domcontentloaded' });
    await this.waitForPageReady();
  }

  /**
   * Get all patterns in the list
   */
  async getPatterns(): Promise<string[]> {
    const patterns = this.page.locator('#autoqueue .pattern span.text');
    return patterns.allInnerTexts();
  }

  /**
   * Get count of patterns
   */
  async getPatternCount(): Promise<number> {
    return this.page.locator('#autoqueue .pattern').count();
  }

  /**
   * Add a new pattern
   */
  async addPattern(pattern: string): Promise<void> {
    await this.page.locator('#add-pattern input').fill(pattern);
    await this.page.locator('#add-pattern .button').click();
    // Wait for the pattern to appear
    await this.page.waitForTimeout(100);
  }

  /**
   * Remove a pattern by index
   */
  async removePattern(index: number): Promise<void> {
    await this.page.locator('#autoqueue .pattern').nth(index).locator('.button').click();
    // Wait for removal
    await this.page.waitForTimeout(100);
  }

  /**
   * Check if the add pattern input is visible
   */
  async isAddPatternInputVisible(): Promise<boolean> {
    return this.page.locator('#add-pattern input').isVisible();
  }
}
