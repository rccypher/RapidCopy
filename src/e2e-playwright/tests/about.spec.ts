import { test, expect } from '@playwright/test';
import { AboutPage } from './pages/about.page';

test.describe('About Page', () => {
  let about: AboutPage;

  test.beforeEach(async ({ page }) => {
    about = new AboutPage(page);
    await about.goto();
  });

  test('should display version in correct format', async () => {
    const version = await about.getVersion();
    expect(version).toMatch(/^v\d+\.\d+\.\d+$/);
  });

  test('should display the current version (v0.8.6)', async () => {
    const version = await about.getVersion();
    expect(version).toBe('v0.8.6');
  });

  test('should have RapidCopy logo/title visible', async () => {
    const isVisible = await about.isContentVisible();
    expect(isVisible).toBe(true);
  });

  test('should display copyright information', async () => {
    const copyright = await about.getCopyright();
    expect(copyright).toContain('Copyright');
    expect(copyright).toContain('2017-2025');
    expect(copyright).toContain('Inderpreet Singh');
  });

  test('should have GitHub link', async () => {
    const hasLink = await about.hasGitHubLink();
    expect(hasLink).toBe(true);
  });

  test('should have correct GitHub URL', async () => {
    const url = await about.getGitHubUrl();
    expect(url).toBe('https://github.com/rccypher/RapidCopy');
  });

  test('should show auto-update not configured message', async () => {
    const hasMessage = await about.hasAutoUpdateMessage();
    expect(hasMessage).toBe(true);
  });

  test('should have Flaticon attribution link', async ({ page }) => {
    const flaticonLink = page.getByRole('link', { name: 'Flaticon' });
    await expect(flaticonLink).toBeVisible();
    await expect(flaticonLink).toHaveAttribute('href', 'https://www.flaticon.com/');
  });
});
