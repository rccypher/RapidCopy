import { test, expect } from './fixtures';
import { DashboardPage } from './pages/dashboard.page';

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
    const files = await dashboard.getFiles();
    expect(files.length).toBeGreaterThan(0);
  });

  test('should have files with expected structure @backend', async () => {
    const files = await dashboard.getFiles();
    
    // Check that each file has required properties
    for (const file of files) {
      expect(file.name).toBeDefined();
      expect(typeof file.name).toBe('string');
      expect(file.size).toBeDefined();
    }
  });

  test('should show and hide action buttons on select @backend', async () => {
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
    const actions = await dashboard.getFileActions(1);
    
    expect(actions.length).toBe(5);
    expect(actions[0].title).toBe('Queue');
    expect(actions[1].title).toBe('Stop');
    expect(actions[2].title).toBe('Extract');
    expect(actions[3].title).toBe('Delete Local');
    expect(actions[4].title).toBe('Delete Remote');
  });

  test('should have Queue action enabled for default state @backend', async () => {
    const files = await dashboard.getFiles();
    expect(files[1].status).toBe('');

    const actions = await dashboard.getFileActions(1);
    expect(actions[0].title).toBe('Queue');
    expect(actions[0].isEnabled).toBe(true);
  });

  test('should have Stop action disabled for default state @backend', async () => {
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
