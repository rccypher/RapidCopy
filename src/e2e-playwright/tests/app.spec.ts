import { test, expect } from '@playwright/test';
import { BasePage } from './fixtures';

test.describe('Top-level App', () => {
  test('should have correct title', async ({ page }) => {
    await page.goto('/');
    
    await expect(page).toHaveTitle('RapidCopy');
  });

  test('should have all sidebar navigation items', async ({ page }) => {
    await page.goto('/');
    
    // Check for main navigation links
    await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Settings' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'AutoQueue' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Logs' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'About' })).toBeVisible();
    
    // Check for Restart button (not a link)
    await expect(page.locator('a').filter({ hasText: 'Restart' })).toBeVisible();
    
    // Check for Dark Mode toggle
    await expect(page.locator('a').filter({ hasText: 'Dark Mode' })).toBeVisible();
  });

  test('should default to the dashboard page', async ({ page }) => {
    await page.goto('/');
    
    // Should redirect to /dashboard
    await expect(page).toHaveURL(/.*dashboard/);
  });

  test('should navigate between pages via sidebar', async ({ page }) => {
    await page.goto('/');

    // Navigate to Settings
    await page.getByRole('link', { name: 'Settings' }).click();
    await expect(page).toHaveURL(/.*settings/);

    // Navigate to AutoQueue
    await page.getByRole('link', { name: 'AutoQueue' }).click();
    await expect(page).toHaveURL(/.*autoqueue/);

    // Navigate to Logs
    await page.getByRole('link', { name: 'Logs' }).click();
    await expect(page).toHaveURL(/.*logs/);

    // Navigate to About
    await page.getByRole('link', { name: 'About' }).click();
    await expect(page).toHaveURL(/.*about/);

    // Navigate back to Dashboard
    await page.getByRole('link', { name: 'Dashboard' }).click();
    await expect(page).toHaveURL(/.*dashboard/);
  });

  test('should toggle dark mode', async ({ page }) => {
    const app = new BasePage(page);
    await page.goto('/');
    
    // Initially in light mode (shows "Dark Mode" toggle)
    await expect(page.locator('a').filter({ hasText: 'Dark Mode' })).toBeVisible();
    
    // Toggle to dark mode
    await app.toggleDarkMode();
    
    // Now shows "Light Mode" toggle
    await expect(page.locator('a').filter({ hasText: 'Light Mode' })).toBeVisible();
    
    // Toggle back to light mode
    await app.toggleDarkMode();
    
    // Back to "Dark Mode" toggle
    await expect(page.locator('a').filter({ hasText: 'Dark Mode' })).toBeVisible();
  });

  test('should show connection error when backend is not running', async ({ page }) => {
    const app = new BasePage(page);
    await page.goto('/');
    
    // The connection error banner should be visible
    const isErrorVisible = await app.isConnectionErrorVisible();
    expect(isErrorVisible).toBe(true);
  });
});
