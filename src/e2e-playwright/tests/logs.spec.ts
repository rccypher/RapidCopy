import { test, expect } from '@playwright/test';
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
});

/**
 * Logs tests that require backend connection
 * These tests are skipped by default - run with: npx playwright test --grep @backend
 */
test.describe('Logs Page - Log Content', () => {
  let logs: LogsPage;

  // Skip all tests in this describe block - they require backend
  test.skip(({ }, testInfo) => true, 'Logs content tests require backend connection');

  test.beforeEach(async ({ page }) => {
    logs = new LogsPage(page);
    await logs.goto();
  });

  test('should display log entries when backend is connected @backend', async () => {
    const count = await logs.getLogEntriesCount();
    expect(count).toBeGreaterThan(0);
  });
});
