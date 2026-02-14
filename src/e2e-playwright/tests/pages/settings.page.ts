import { Page } from '@playwright/test';
import { BasePage } from '../fixtures';

/**
 * Represents a path pair item displayed in settings
 */
export interface PathPairItem {
  name: string;
  remotePath: string;
  localPath: string;
  isEnabled: boolean;
  hasAutoQueue: boolean;
}

/**
 * Settings page object
 */
export class SettingsPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  /**
   * Navigate to the settings page
   */
  async goto(): Promise<void> {
    await this.page.goto('/settings');
    await this.waitForPageReady();
  }

  // ==================== Path Pairs Section ====================

  /**
   * Check if Path Pairs section is visible
   */
  async isPathPairsSectionVisible(): Promise<boolean> {
    return this.page.getByRole('heading', { name: 'Path Pairs' }).isVisible();
  }

  /**
   * Check if Add Path Pair button is present
   */
  async isAddPathPairButtonPresent(): Promise<boolean> {
    return this.page.getByRole('button', { name: '+ Add Path Pair' }).isVisible();
  }

  /**
   * Click the Add Path Pair button
   */
  async clickAddPathPairButton(): Promise<void> {
    await this.page.getByRole('button', { name: '+ Add Path Pair' }).click();
  }

  /**
   * Check if the New Path Pair form is displayed
   */
  async isPathPairFormDisplayed(): Promise<boolean> {
    return this.page.getByRole('heading', { name: 'New Path Pair' }).isVisible();
  }

  /**
   * Fill in the path pair form
   */
  async fillPathPairForm(name: string, remotePath: string, localPath: string): Promise<void> {
    await this.page.getByRole('textbox', { name: 'Name' }).fill(name);
    await this.page.getByRole('textbox', { name: 'Remote Path *' }).fill(remotePath);
    await this.page.getByRole('textbox', { name: 'Local Path *' }).fill(localPath);
  }

  /**
   * Toggle the Enabled checkbox in path pair form
   */
  async togglePathPairEnabled(): Promise<void> {
    await this.page.getByRole('checkbox', { name: 'Enabled' }).click();
  }

  /**
   * Toggle the Auto-queue checkbox in path pair form
   */
  async togglePathPairAutoQueue(): Promise<void> {
    await this.page.getByRole('checkbox', { name: 'Auto-queue new files' }).click();
  }

  /**
   * Click Save button in path pair form
   */
  async clickPathPairSave(): Promise<void> {
    await this.page.getByRole('button', { name: 'Save' }).click();
  }

  /**
   * Click Cancel button in path pair form
   */
  async clickPathPairCancel(): Promise<void> {
    await this.page.getByRole('button', { name: 'Cancel' }).click();
  }

  /**
   * Check if empty state is displayed for path pairs
   */
  async isPathPairsEmptyStateDisplayed(): Promise<boolean> {
    return this.page.getByText('No path pairs configured yet.').isVisible();
  }

  // ==================== Network Mounts Section ====================

  /**
   * Check if Network Mounts section is visible
   */
  async isNetworkMountsSectionVisible(): Promise<boolean> {
    return this.page.getByRole('heading', { name: 'Network Mounts' }).isVisible();
  }

  /**
   * Check if Add Network Mount button is present
   */
  async isAddNetworkMountButtonPresent(): Promise<boolean> {
    return this.page.getByRole('button', { name: '+ Add Network Mount' }).isVisible();
  }

  /**
   * Check if empty state is displayed for network mounts
   */
  async isNetworkMountsEmptyStateDisplayed(): Promise<boolean> {
    return this.page.getByText('No network mounts configured yet.').isVisible();
  }

  // ==================== Server Section ====================

  /**
   * Check if Server section is visible
   */
  async isServerSectionVisible(): Promise<boolean> {
    return this.page.getByRole('heading', { name: 'Server' }).isVisible();
  }

  /**
   * Get Server Address field value
   */
  async getServerAddress(): Promise<string> {
    return this.page.getByRole('textbox', { name: 'Server Address' }).inputValue();
  }

  /**
   * Check if Server Address field is disabled
   */
  async isServerAddressDisabled(): Promise<boolean> {
    return this.page.getByRole('textbox', { name: 'Server Address' }).isDisabled();
  }

  // ==================== Connections Section ====================

  /**
   * Check if Connections section is visible
   */
  async isConnectionsSectionVisible(): Promise<boolean> {
    return this.page.getByRole('heading', { name: 'Connections' }).isVisible();
  }

  // ==================== AutoQueue Section ====================

  /**
   * Check if AutoQueue section is visible
   */
  async isAutoQueueSectionVisible(): Promise<boolean> {
    return this.page.getByRole('heading', { name: 'AutoQueue' }).first().isVisible();
  }

  // ==================== Archive Extraction Section ====================

  /**
   * Check if Archive Extraction section is visible
   */
  async isArchiveExtractionSectionVisible(): Promise<boolean> {
    return this.page.getByRole('heading', { name: 'Archive Extraction' }).isVisible();
  }

  // ==================== File Discovery Section ====================

  /**
   * Check if File Discovery section is visible
   */
  async isFileDiscoverySectionVisible(): Promise<boolean> {
    return this.page.getByRole('heading', { name: 'File Discovery' }).isVisible();
  }

  // ==================== Other Settings Section ====================

  /**
   * Check if Other Settings section is visible
   */
  async isOtherSettingsSectionVisible(): Promise<boolean> {
    return this.page.getByRole('heading', { name: 'Other Settings' }).isVisible();
  }

  // ==================== Restart Button ====================

  /**
   * Check if Restart button is visible at bottom
   */
  async isRestartButtonVisible(): Promise<boolean> {
    // The restart button at the bottom of settings page
    return this.page.locator('button').filter({ hasText: 'Restart' }).last().isVisible();
  }
}
