import { test, expect } from './fixtures';
import { DashboardPage } from './pages/dashboard.page';

/**
 * Dashboard UI-only tests (no backend required)
 */
test.describe('Dashboard Page - UI Structure', () => {
  let dashboard: DashboardPage;

  test.beforeEach(async ({ page }) => {
    dashboard = new DashboardPage(page);
    await dashboard.goto();
  });

  test('should display file list container', async () => {
    const fileList = dashboard.page.locator('#file-list');
    await expect(fileList).toBeVisible();
  });

  test('should display file list header with all columns', async () => {
    await expect(dashboard.page.locator('#file-list #header .name')).toHaveText('Filename');
    await expect(dashboard.page.locator('#file-list #header .status')).toHaveText('Status');
    await expect(dashboard.page.locator('#file-list #header .speed')).toHaveText('Speed');
    await expect(dashboard.page.locator('#file-list #header .eta')).toHaveText('ETA');
    await expect(dashboard.page.locator('#file-list #header .size')).toHaveText('Size');
  });

  test('should display filter search input', async () => {
    const filterInput = dashboard.page.locator('#file-options #filter-search input');
    await expect(filterInput).toBeVisible();
    await expect(filterInput).toHaveAttribute('placeholder', 'Filter by name...');
  });

  test('should display status filter dropdown', async () => {
    const statusFilter = dashboard.page.locator('#file-options #filter-status');
    await expect(statusFilter).toBeVisible();
    await expect(statusFilter.locator('.title')).toHaveText('Status:');
  });

  test('should display sort dropdown', async () => {
    const sortDropdown = dashboard.page.locator('#file-options #sort-status');
    await expect(sortDropdown).toBeVisible();
    await expect(sortDropdown.locator('.title')).toHaveText('Sort:');
  });

  test('should display details toggle button', async () => {
    const detailsBtn = dashboard.page.locator('#file-options #toggle-details');
    await expect(detailsBtn).toBeVisible();
    await expect(detailsBtn.locator('.title')).toHaveText('Details:');
  });

  test('should display pin filter button', async () => {
    const pinBtn = dashboard.page.locator('#file-options #pin-filter');
    await expect(pinBtn).toBeVisible();
  });

  test('should show connection error banner when backend not running', async () => {
    const isErrorVisible = await dashboard.isConnectionErrorVisible();
    expect(isErrorVisible).toBe(true);
  });

  test('should highlight Dashboard in sidebar as active', async () => {
    const activeLink = dashboard.page.locator('a.selected').filter({ hasText: 'Dashboard' });
    await expect(activeLink).toBeVisible();
  });
});

/**
 * Dashboard tests that require backend connection
 * Run with: npx playwright test --project=with-backend
 * Or run all tests with: npx playwright test --project=all
 */
test.describe('Dashboard Page @backend', () => {
  let dashboard: DashboardPage;

  test.beforeEach(async ({ page, backendAvailable }) => {
    // Skip if backend is not available (safety check)
    test.skip(!backendAvailable, 'Backend is not available');
    
    dashboard = new DashboardPage(page);
    await dashboard.goto();
  });

  test('should have correct top title @backend', async () => {
    const title = await dashboard.getTopTitle();
    expect(title).toBe('Dashboard');
  });

  test('should display a list of files @backend', async () => {
    // Wait for files to load via SSE stream (may take a moment)
    await dashboard.waitForFileList();
    const files = await dashboard.getFiles();
    expect(files.length).toBeGreaterThan(0);
  });

  test('should have files with expected structure @backend', async () => {
    // Wait for files to load via SSE stream
    await dashboard.waitForFileList();
    const files = await dashboard.getFiles();
    
    // Check that each file has required properties
    for (const file of files) {
      expect(file.name).toBeDefined();
      expect(typeof file.name).toBe('string');
      expect(file.size).toBeDefined();
    }
  });

  test('should show and hide action buttons on select @backend', async () => {
    // Wait for files to load
    await dashboard.waitForFileList();
    // Initially actions should not be visible
    const initiallyVisible = await dashboard.isFileActionsVisible(1);
    expect(initiallyVisible).toBe(false);

    // Click to select - actions should appear
    await dashboard.selectFile(1);
    const afterSelect = await dashboard.isFileActionsVisible(1);
    expect(afterSelect).toBe(true);

    // Click again to deselect - actions should hide
    await dashboard.selectFile(1);
    const afterDeselect = await dashboard.isFileActionsVisible(1);
    expect(afterDeselect).toBe(false);
  });

  test('should show action buttons for most recently selected file only @backend', async () => {
    // Wait for files to load
    await dashboard.waitForFileList();
    // Select first file
    await dashboard.selectFile(1);
    expect(await dashboard.isFileActionsVisible(1)).toBe(true);
    expect(await dashboard.isFileActionsVisible(2)).toBe(false);

    // Select second file - first should hide, second should show
    await dashboard.selectFile(2);
    expect(await dashboard.isFileActionsVisible(1)).toBe(false);
    expect(await dashboard.isFileActionsVisible(2)).toBe(true);

    // Deselect second file
    await dashboard.selectFile(2);
    expect(await dashboard.isFileActionsVisible(1)).toBe(false);
    expect(await dashboard.isFileActionsVisible(2)).toBe(false);
  });

  test('should have all action buttons @backend', async () => {
    // Wait for files to load
    await dashboard.waitForFileList();
    const actions = await dashboard.getFileActions(1);
    
    expect(actions.length).toBe(5);
    expect(actions[0].title).toBe('Queue');
    expect(actions[1].title).toBe('Stop');
    expect(actions[2].title).toBe('Extract');
    expect(actions[3].title).toBe('Delete Local');
    expect(actions[4].title).toBe('Delete Remote');
  });

  test('should have Queue action enabled for default state @backend', async () => {
    // Wait for files to load
    await dashboard.waitForFileList();
    const files = await dashboard.getFiles();
    expect(files[1].status).toBe('');

    const actions = await dashboard.getFileActions(1);
    expect(actions[0].title).toBe('Queue');
    expect(actions[0].isEnabled).toBe(true);
  });

  test('should have Stop action disabled for default state @backend', async () => {
    // Wait for files to load
    await dashboard.waitForFileList();
    const files = await dashboard.getFiles();
    expect(files[1].status).toBe('');

    const actions = await dashboard.getFileActions(1);
    expect(actions[1].title).toBe('Stop');
    expect(actions[1].isEnabled).toBe(false);
  });
});

/**
 * Dashboard Multi-Path tests that require backend connection
 */
test.describe('Dashboard Multi-Path Features @backend', () => {
  let dashboard: DashboardPage;

  test.beforeEach(async ({ page, backendAvailable }) => {
    // Skip if backend is not available (safety check)
    test.skip(!backendAvailable, 'Backend is not available');
    
    dashboard = new DashboardPage(page);
    await dashboard.goto();
  });

  test('should check if path pair stats is present @backend', async () => {
    const isPresent = await dashboard.isPathPairStatsPresent();
    expect(typeof isPresent).toBe('boolean');
  });

  test('should display files list @backend', async () => {
    // Wait for files to load via SSE
    await dashboard.waitForFileList();
    const fileCount = await dashboard.getFileCount();
    expect(fileCount).toBeGreaterThan(0);
  });

  test('should show stats component header when multiple path pairs exist @backend', async () => {
    const isPresent = await dashboard.isPathPairStatsPresent();
    if (isPresent) {
      const title = await dashboard.getPathPairStatsTitle();
      expect(title).toBe('Path Pair Statistics');
    }
  });

  test('should toggle stats expansion when clicking header @backend', async () => {
    const isPresent = await dashboard.isPathPairStatsPresent();
    if (isPresent) {
      const initialState = await dashboard.isPathPairStatsExpanded();
      await dashboard.togglePathPairStats();
      const newState = await dashboard.isPathPairStatsExpanded();
      expect(newState).toBe(!initialState);

      // Toggle back
      await dashboard.togglePathPairStats();
    }
  });

  test('should display stat cards for each path pair @backend', async () => {
    const isPresent = await dashboard.isPathPairStatsPresent();
    if (isPresent) {
      const cardCount = await dashboard.getPathPairStatCardCount();
      expect(cardCount).toBeGreaterThan(0);
    }
  });
});
