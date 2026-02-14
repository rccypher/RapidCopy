import { test as base, expect, Page, Locator } from '@playwright/test';

/**
 * Base page object providing common functionality for all pages
 */
export class BasePage {
  readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  /**
   * Get the page title from browser
   */
  async getTitle(): Promise<string> {
    return this.page.title();
  }

  /**
   * Get the top title element text (the active sidebar item)
   * Note: RapidCopy doesn't have a separate title element - we check active nav item
   */
  async getTopTitle(): Promise<string> {
    // The active page is indicated by the sidebar link with 'active' class
    // Try multiple selectors to find the active navigation item
    const selectors = [
      'a.active',
      '.sidebar a.active',
      'nav a.active',
      '.nav-item.active a',
      'a[class*="active"]'
    ];
    
    for (const selector of selectors) {
      const link = this.page.locator(selector).first();
      if (await link.count() > 0) {
        const text = await link.innerText();
        return text.trim();
      }
    }
    
    // Fallback: check URL to determine current page
    const url = this.page.url();
    if (url.includes('/dashboard')) return 'Dashboard';
    if (url.includes('/settings')) return 'Settings';
    if (url.includes('/autoqueue')) return 'AutoQueue';
    if (url.includes('/logs')) return 'Logs';
    if (url.includes('/about')) return 'About';
    
    return '';
  }

  /**
   * Get all sidebar navigation items (excluding Dark Mode toggle)
   */
  async getSidebarItems(): Promise<string[]> {
    // Get all navigation links in the sidebar
    const items = await this.page.locator('a[href^="/"]').allInnerTexts();
    return items.map(item => item.trim()).filter(item => item.length > 0);
  }

  /**
   * Navigate to a page via sidebar
   */
  async navigateViaSidebar(pageName: string): Promise<void> {
    await this.page.getByRole('link', { name: pageName }).click();
  }

  /**
   * Check if the connection error banner is visible
   */
  async isConnectionErrorVisible(): Promise<boolean> {
    const errorBanner = this.page.getByText('Lost connection to the RapidCopy service.');
    return errorBanner.isVisible();
  }

  /**
   * Toggle dark mode
   */
  async toggleDarkMode(): Promise<void> {
    const toggle = this.page.locator('a').filter({ hasText: /Dark Mode|Light Mode/ });
    await toggle.click();
  }

  /**
   * Check if dark mode is currently active
   */
  async isDarkModeActive(): Promise<boolean> {
    const lightModeToggle = this.page.locator('a').filter({ hasText: 'Light Mode' });
    return lightModeToggle.isVisible();
  }

  /**
   * Wait for the page to be ready (loading complete)
   * Note: We use 'domcontentloaded' instead of 'networkidle' because
   * RapidCopy maintains a persistent WebSocket connection that prevents
   * networkidle from ever completing.
   */
  async waitForPageReady(): Promise<void> {
    // Wait for DOM content to load - networkidle doesn't work due to WebSocket
    await this.page.waitForLoadState('domcontentloaded');
    // Also wait for any Angular app to bootstrap by checking for app-root content
    await this.page.locator('app-root').waitFor({ state: 'attached', timeout: 10000 });
  }
}

/**
 * Check if backend is available by making a health check request
 */
export async function isBackendAvailable(page: Page): Promise<boolean> {
  try {
    const response = await page.request.get('/server/status', { timeout: 5000 });
    return response.ok();
  } catch {
    return false;
  }
}

/**
 * Extended test fixtures with common setup
 */
export const test = base.extend<{
  backendAvailable: boolean;
}>({
  /**
   * Fixture that checks if backend is available
   * Use this in tests to conditionally skip if backend is not running
   */
  backendAvailable: [async ({ page }, use) => {
    const available = await isBackendAvailable(page);
    await use(available);
  }, { timeout: 10000 }],
});

export { expect };
