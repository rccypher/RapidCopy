/**
 * Integration tests for the QA Docker environment.
 * 
 * These tests verify that all components of the QA environment are working together:
 * - RapidCopy backend and frontend
 * - Remote SSH server (seedbox simulator)
 * - Path pairs configuration
 * - File synchronization workflow
 * 
 * Prerequisites:
 *   docker-compose -f docker-compose.qa.yml up --build
 * 
 * Run these tests:
 *   RAPIDCOPY_URL=http://localhost:8800 npx playwright test tests/integration/
 * 
 * @tags @integration @backend @qa
 */
import { test, expect } from '../fixtures';
import { DashboardPage } from '../pages/dashboard.page';
import { SettingsPage } from '../pages/settings.page';
import { LogsPage } from '../pages/logs.page';

test.describe('QA Environment Integration Tests @integration @backend', () => {

  test.describe('Backend Connectivity', () => {
    
    test('should have backend available', async ({ page, backendAvailable }) => {
      test.skip(!backendAvailable, 'Backend is not available');
      expect(backendAvailable).toBe(true);
    });

    test('should return server status', async ({ page, backendAvailable }) => {
      test.skip(!backendAvailable, 'Backend is not available');
      
      const response = await page.request.get('/server/status');
      expect(response.ok()).toBe(true);
      
      const status = await response.json();
      expect(status).toHaveProperty('server');
    });

    test('should return config data', async ({ page, backendAvailable }) => {
      test.skip(!backendAvailable, 'Backend is not available');
      
      const response = await page.request.get('/server/config/get');
      expect(response.ok()).toBe(true);
      
      const config = await response.json();
      expect(config).toBeDefined();
    });
  });

  test.describe('Remote Server Configuration', () => {
    
    test('should have remote server configured', async ({ page, backendAvailable }) => {
      test.skip(!backendAvailable, 'Backend is not available');
      
      const settingsPage = new SettingsPage(page);
      await settingsPage.goto();
      
      // Server section should be visible
      await expect(await settingsPage.isServerSectionVisible()).toBe(true);
      
      // Server address should be configured (not empty)
      const serverAddress = await settingsPage.getServerAddress();
      // In QA environment, should be configured to 'remote' or 'localhost'
      expect(serverAddress.length).toBeGreaterThan(0);
    });
  });

  test.describe('Path Pairs', () => {
    
    test('should display path pairs section', async ({ page, backendAvailable }) => {
      test.skip(!backendAvailable, 'Backend is not available');
      
      const settingsPage = new SettingsPage(page);
      await settingsPage.goto();
      
      expect(await settingsPage.isPathPairsSectionVisible()).toBe(true);
    });

    test('should allow adding a new path pair', async ({ page, backendAvailable }) => {
      test.skip(!backendAvailable, 'Backend is not available');
      
      const settingsPage = new SettingsPage(page);
      await settingsPage.goto();
      
      // Click Add Path Pair button
      await settingsPage.clickAddPathPairButton();
      
      // Form should be displayed
      expect(await settingsPage.isPathPairFormDisplayed()).toBe(true);
      
      // Fill in the form with test data
      await settingsPage.fillPathPairForm(
        'Test Path Pair',
        '/home/remoteuser/files/test',
        '/downloads/test'
      );
      
      // Cancel to avoid modifying state
      await settingsPage.clickPathPairCancel();
    });
  });

  test.describe('Dashboard File List', () => {
    
    test('should load dashboard with file list', async ({ page, backendAvailable }) => {
      test.skip(!backendAvailable, 'Backend is not available');
      
      const dashboardPage = new DashboardPage(page);
      
      // Navigate and wait for file list
      await page.goto('/dashboard');
      await page.waitForLoadState('networkidle');
      
      // Either we see files or we see a message about no files
      const fileList = page.locator('#file-list');
      await expect(fileList).toBeVisible({ timeout: 10000 });
    });

    test('should show file details when files are present', async ({ page, backendAvailable }) => {
      test.skip(!backendAvailable, 'Backend is not available');
      
      const dashboardPage = new DashboardPage(page);
      await page.goto('/dashboard');
      await page.waitForLoadState('networkidle');
      
      // Check if there are any files
      const fileCount = await page.locator('#file-list .file').count();
      
      if (fileCount > 0) {
        // Get file info
        const files = await dashboardPage.getFiles();
        expect(files.length).toBeGreaterThan(0);
        
        // Each file should have a name
        for (const file of files) {
          expect(file.name.length).toBeGreaterThan(0);
        }
      }
    });
  });

  test.describe('Logs', () => {
    
    test('should display logs page', async ({ page, backendAvailable }) => {
      test.skip(!backendAvailable, 'Backend is not available');
      
      const logsPage = new LogsPage(page);
      await logsPage.goto();
      
      // Logs page should load successfully
      expect(await logsPage.isLogListPresent()).toBe(true);
    });

    test('should have log entries after startup', async ({ page, backendAvailable }) => {
      test.skip(!backendAvailable, 'Backend is not available');
      
      const logsPage = new LogsPage(page);
      await logsPage.goto();
      
      // There should be some log entries from startup
      const logCount = await logsPage.getLogEntryCount();
      expect(logCount).toBeGreaterThan(0);
    });
  });

  test.describe('API Endpoints', () => {
    
    test('should return file list from API', async ({ page, backendAvailable }) => {
      test.skip(!backendAvailable, 'Backend is not available');
      
      const response = await page.request.get('/server/model-files/get');
      expect(response.ok()).toBe(true);
      
      const data = await response.json();
      expect(data).toBeDefined();
      // Should be an object with files
      expect(typeof data).toBe('object');
    });

    test('should return path pairs from API', async ({ page, backendAvailable }) => {
      test.skip(!backendAvailable, 'Backend is not available');
      
      const response = await page.request.get('/server/path-pairs/get');
      expect(response.ok()).toBe(true);
      
      const data = await response.json();
      expect(Array.isArray(data)).toBe(true);
    });

    test('should return logs from API', async ({ page, backendAvailable }) => {
      test.skip(!backendAvailable, 'Backend is not available');
      
      const response = await page.request.get('/server/log/get');
      expect(response.ok()).toBe(true);
      
      const data = await response.json();
      expect(Array.isArray(data)).toBe(true);
    });

    test('should return autoqueue patterns from API', async ({ page, backendAvailable }) => {
      test.skip(!backendAvailable, 'Backend is not available');
      
      const response = await page.request.get('/server/autoqueue/get');
      expect(response.ok()).toBe(true);
      
      const data = await response.json();
      expect(Array.isArray(data)).toBe(true);
    });
  });

  test.describe('Network Mounts', () => {
    
    test('should display network mounts section in settings', async ({ page, backendAvailable }) => {
      test.skip(!backendAvailable, 'Backend is not available');
      
      const settingsPage = new SettingsPage(page);
      await settingsPage.goto();
      
      expect(await settingsPage.isNetworkMountsSectionVisible()).toBe(true);
    });

    test('should return network mounts from API', async ({ page, backendAvailable }) => {
      test.skip(!backendAvailable, 'Backend is not available');
      
      const response = await page.request.get('/server/network-mounts/get');
      expect(response.ok()).toBe(true);
      
      const data = await response.json();
      expect(Array.isArray(data)).toBe(true);
    });
  });
});

test.describe('QA Environment Health Checks @integration @backend', () => {
  
  test('full application health check', async ({ page, backendAvailable }) => {
    test.skip(!backendAvailable, 'Backend is not available');
    
    // 1. Check server status API
    const statusResponse = await page.request.get('/server/status');
    expect(statusResponse.ok()).toBe(true);
    
    // 2. Check dashboard loads
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');
    const dashboardLoaded = await page.locator('#file-list').isVisible();
    expect(dashboardLoaded).toBe(true);
    
    // 3. Check settings loads
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');
    const settingsLoaded = await page.getByRole('heading', { name: 'Path Pairs' }).isVisible();
    expect(settingsLoaded).toBe(true);
    
    // 4. Check logs loads
    await page.goto('/logs');
    await page.waitForLoadState('networkidle');
    const logsLoaded = await page.locator('.log-list').isVisible();
    expect(logsLoaded).toBe(true);
    
    // 5. Check about page loads
    await page.goto('/about');
    await page.waitForLoadState('networkidle');
    const aboutLoaded = await page.getByText('RapidCopy').first().isVisible();
    expect(aboutLoaded).toBe(true);
  });

  test('websocket connection health', async ({ page, backendAvailable }) => {
    test.skip(!backendAvailable, 'Backend is not available');
    
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');
    
    // Give time for websocket to connect
    await page.waitForTimeout(2000);
    
    // Check that there's no connection error banner
    const connectionError = page.getByText('Lost connection to the RapidCopy service.');
    const hasError = await connectionError.isVisible();
    expect(hasError).toBe(false);
  });
});
