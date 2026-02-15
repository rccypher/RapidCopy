import { test, expect } from './fixtures';
import { LogsPage } from './pages/logs.page';

test.describe('Logs Page - UI Elements', () => {
  let logs: LogsPage;

  test.beforeEach(async ({ page }) => {
    logs = new LogsPage(page);
    await logs.goto();
  });

  test('should have correct top title', async () => {
    const title = await logs.getTopTitle();
    expect(title).toBe('Logs');
  });

  test('should display logs container', async () => {
    const isVisible = await logs.isLogsContainerVisible();
    expect(isVisible).toBe(true);
  });

  test('should have scroll to top button present in DOM', async () => {
    const btn = logs.page.locator('#btn-scroll-top');
    await expect(btn).toBeAttached();
    await expect(btn).toHaveText('Scroll To Top');
  });

  test('should have scroll to bottom button present in DOM', async () => {
    const btn = logs.page.locator('#btn-scroll-bottom');
    await expect(btn).toBeAttached();
    await expect(btn).toHaveText('Scroll To Bottom');
  });

  test('should have scroll buttons hidden by default (no logs)', async () => {
    const topVisible = await logs.isScrollToTopButtonVisible();
    const bottomVisible = await logs.isScrollToBottomButtonVisible();
    expect(topVisible).toBe(false);
    expect(bottomVisible).toBe(false);
  });

  test('should have log marker elements for scroll anchoring', async () => {
    const logHead = logs.page.locator('.log-marker').first();
    const logTail = logs.page.locator('.log-marker').last();
    await expect(logHead).toBeAttached();
    await expect(logTail).toBeAttached();
  });

  test('should highlight Logs in sidebar as active', async () => {
    const activeLink = logs.page.locator('a.selected').filter({ hasText: 'Logs' });
    await expect(activeLink).toBeVisible();
  });

  test('should show connection error banner when backend not running', async () => {
    const isErrorVisible = await logs.isConnectionErrorVisible();
    expect(isErrorVisible).toBe(true);
  });

  test('should have zero log entries when backend not connected', async () => {
    const count = await logs.getLogEntriesCount();
    expect(count).toBe(0);
  });
});

/**
 * Logs tests that require backend connection
 * Run with: npx playwright test --project=with-backend
 */
test.describe('Logs Page - Log Content @backend', () => {
  let logs: LogsPage;

  test.beforeEach(async ({ page, backendAvailable }) => {
    // Skip if backend is not available (safety check)
    test.skip(!backendAvailable, 'Backend is not available');
    
    logs = new LogsPage(page);
    await logs.goto();
  });

  test('should display log entries when backend is connected @backend', async () => {
    const count = await logs.getLogEntriesCount();
    expect(count).toBeGreaterThan(0);
  });
});
