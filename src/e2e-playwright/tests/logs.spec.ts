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
