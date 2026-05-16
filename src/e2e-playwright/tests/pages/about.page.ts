import { Page } from '@playwright/test';
import { BasePage } from '../fixtures';

/**
 * About page object
 */
export class AboutPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  /**
   * Navigate to the about page
   */
  async goto(): Promise<void> {
    // Use domcontentloaded to avoid waiting for WebSocket to complete
    await this.page.goto('/about', { waitUntil: 'domcontentloaded' });
    await this.waitForPageReady();
  }

  /**
   * Get the version string displayed (e.g., "v0.8.6")
   */
  async getVersion(): Promise<string> {
    // Version is displayed as text starting with 'v'
    const versionElement = this.page.getByText(/^v\d+\.\d+\.\d+/);
    return versionElement.innerText();
  }

  /**
   * Check if the about content is visible
   */
  async isContentVisible(): Promise<boolean> {
    // Check if the RapidCopy title/logo is visible (wait for it to load)
    const img = this.page.getByRole('img', { name: 'RapidCopy' });
    await img.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
    return img.isVisible();
  }

  /**
   * Get the copyright text
   */
  async getCopyright(): Promise<string> {
    return this.page.getByText(/Copyright/).innerText();
  }

  /**
   * Check if GitHub link is present
   */
  async hasGitHubLink(): Promise<boolean> {
    return this.page.getByRole('link', { name: 'GitHub' }).isVisible();
  }

  /**
   * Get the GitHub link URL
   */
  async getGitHubUrl(): Promise<string | null> {
    return this.page.getByRole('link', { name: 'GitHub' }).getAttribute('href');
  }

  /**
   * Check if auto-update message is visible
   */
  async hasAutoUpdateMessage(): Promise<boolean> {
    return this.page.getByText(/Auto-update is not configured/).isVisible();
  }
}
