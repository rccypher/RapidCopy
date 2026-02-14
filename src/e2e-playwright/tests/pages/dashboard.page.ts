import { Page } from '@playwright/test';
import { BasePage } from '../fixtures';

/**
 * Represents a file in the dashboard file list
 */
export interface FileInfo {
  name: string;
  status: string;
  size: string;
}

/**
 * Represents the state of a file action button
 */
export interface FileActionButton {
  title: string;
  isEnabled: boolean;
}

/**
 * Dashboard page object
 */
export class DashboardPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  /**
   * Navigate to the dashboard page
   */
  async goto(): Promise<void> {
    // Use domcontentloaded to avoid waiting for WebSocket to complete
    await this.page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await this.waitForDashboardReady();
  }

  /**
   * Wait for the dashboard to be ready (either files present or empty state)
   */
  async waitForDashboardReady(): Promise<void> {
    // Wait for the file-list container to be present (regardless of content)
    await this.page.locator('#file-list').waitFor({ state: 'visible', timeout: 10000 });
  }

  /**
   * Wait for files to appear in the list (use only when files are expected)
   * Handles SSE reconnection - may need to wait for connection to be established
   */
  async waitForFileList(): Promise<void> {
    // Wait up to 30 seconds for files to appear (SSE may need time to reconnect)
    await this.page.locator('#file-list .file').first().waitFor({ state: 'visible', timeout: 30000 });
  }

  /**
   * Check if there are any files in the list
   */
  async hasFiles(): Promise<boolean> {
    const count = await this.page.locator('#file-list .file').count();
    return count > 0;
  }

  /**
   * Get all files displayed in the list
   */
  async getFiles(): Promise<FileInfo[]> {
    const fileElements = this.page.locator('#file-list .file');
    const count = await fileElements.count();
    const files: FileInfo[] = [];

    for (let i = 0; i < count; i++) {
      const file = fileElements.nth(i);
      const name = await file.locator('.name .text').innerText();
      
      // Status may not be present
      const statusLocator = file.locator('.content .status span.text');
      const status = await statusLocator.count() > 0 ? await statusLocator.innerText() : '';
      
      const size = await file.locator('.size .size_info').innerText();
      
      files.push({ name: name.trim(), status, size });
    }

    return files;
  }

  /**
   * Get count of files in the list
   */
  async getFileCount(): Promise<number> {
    return this.page.locator('#file-list .file').count();
  }

  /**
   * Select/click on a file by index
   */
  async selectFile(index: number): Promise<void> {
    await this.page.locator('#file-list .file').nth(index).click();
  }

  /**
   * Check if file actions are visible for a file
   */
  async isFileActionsVisible(index: number): Promise<boolean> {
    const actions = this.page.locator('#file-list .file').nth(index).locator('.actions');
    return actions.isVisible();
  }

  /**
   * Get file action buttons for a file
   */
  async getFileActions(index: number): Promise<FileActionButton[]> {
    // First select the file to show actions
    await this.selectFile(index);
    await this.page.locator('#file-list .file').nth(index).locator('.actions').waitFor({ state: 'visible' });

    const buttons = this.page.locator('#file-list .file').nth(index).locator('.actions .button');
    const count = await buttons.count();
    const actions: FileActionButton[] = [];

    for (let i = 0; i < count; i++) {
      const button = buttons.nth(i);
      const title = await button.locator('div.text span').innerText();
      const isDisabled = await button.getAttribute('disabled');
      actions.push({ title, isEnabled: isDisabled === null });
    }

    return actions;
  }

  /**
   * Click a specific action button on a file
   */
  async clickFileAction(fileIndex: number, actionTitle: string): Promise<void> {
    await this.selectFile(fileIndex);
    await this.page.locator('#file-list .file').nth(fileIndex)
      .locator('.actions .button', { hasText: actionTitle })
      .click();
  }

  /**
   * Check if path pair stats component is present (multi-path mode)
   */
  async isPathPairStatsPresent(): Promise<boolean> {
    return this.page.locator('.path-pair-stats-container').isVisible();
  }

  /**
   * Get path pair statistics title
   */
  async getPathPairStatsTitle(): Promise<string> {
    return this.page.locator('.path-pair-stats-container .header .title span').innerText();
  }

  /**
   * Toggle path pair stats expansion
   */
  async togglePathPairStats(): Promise<void> {
    await this.page.locator('.path-pair-stats-container .header').click();
  }

  /**
   * Check if path pair stats is expanded
   */
  async isPathPairStatsExpanded(): Promise<boolean> {
    return this.page.locator('.path-pair-stats-container .stats-grid').isVisible();
  }

  /**
   * Get count of path pair stat cards
   */
  async getPathPairStatCardCount(): Promise<number> {
    return this.page.locator('.path-pair-stats-container .path-pair-card').count();
  }

  /**
   * Check if any file has a path pair badge
   */
  async hasAnyPathPairBadge(): Promise<boolean> {
    const count = await this.page.locator('#file-list .file .path-pair-badge').count();
    return count > 0;
  }

  /**
   * Get unique path pair names from file badges
   */
  async getUniquePathPairNames(): Promise<string[]> {
    const badges = this.page.locator('#file-list .file .path-pair-badge');
    const names = await badges.allInnerTexts();
    return [...new Set(names)];
  }
}
