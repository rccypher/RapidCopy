import { test, expect } from './fixtures';
import { SettingsPage } from './pages/settings.page';

test.describe('Settings Page - Layout', () => {
  let settings: SettingsPage;

  test.beforeEach(async ({ page }) => {
    settings = new SettingsPage(page);
    await settings.goto();
  });

  test('should display Path Pairs section', async () => {
    const isVisible = await settings.isPathPairsSectionVisible();
    expect(isVisible).toBe(true);
  });

  test('should display Network Mounts section', async () => {
    const isVisible = await settings.isNetworkMountsSectionVisible();
    expect(isVisible).toBe(true);
  });

  test('should display Server section', async () => {
    const isVisible = await settings.isServerSectionVisible();
    expect(isVisible).toBe(true);
  });

  test('should display Connections section', async () => {
    const isVisible = await settings.isConnectionsSectionVisible();
    expect(isVisible).toBe(true);
  });

  test('should display AutoQueue section', async () => {
    const isVisible = await settings.isAutoQueueSectionVisible();
    expect(isVisible).toBe(true);
  });

  test('should display Archive Extraction section', async () => {
    const isVisible = await settings.isArchiveExtractionSectionVisible();
    expect(isVisible).toBe(true);
  });

  test('should display File Discovery section', async () => {
    const isVisible = await settings.isFileDiscoverySectionVisible();
    expect(isVisible).toBe(true);
  });

  test('should display Other Settings section', async () => {
    const isVisible = await settings.isOtherSettingsSectionVisible();
    expect(isVisible).toBe(true);
  });

  test('should have fields disabled when backend not connected', async () => {
    const isDisabled = await settings.isServerAddressDisabled();
    expect(isDisabled).toBe(true);
  });

  test('should highlight Settings in sidebar as active', async () => {
    const activeLink = settings.page.locator('a.selected').filter({ hasText: 'Settings' });
    await expect(activeLink).toBeVisible();
  });

  test('should show connection error banner when backend not running', async () => {
    const isErrorVisible = await settings.isConnectionErrorVisible();
    expect(isErrorVisible).toBe(true);
  });

  test('should display Restart button', async () => {
    const isVisible = await settings.isRestartButtonVisible();
    expect(isVisible).toBe(true);
  });
});

test.describe('Settings Page - Path Pairs', () => {
  let settings: SettingsPage;

  test.beforeEach(async ({ page }) => {
    settings = new SettingsPage(page);
    await settings.goto();
  });

  test('should have Add Path Pair button', async () => {
    const isPresent = await settings.isAddPathPairButtonPresent();
    expect(isPresent).toBe(true);
  });

  test('should show empty state when no path pairs configured', async () => {
    const isEmpty = await settings.isPathPairsEmptyStateDisplayed();
    expect(isEmpty).toBe(true);
  });

  test('should show form when clicking Add Path Pair button', async () => {
    await settings.clickAddPathPairButton();
    
    const isFormDisplayed = await settings.isPathPairFormDisplayed();
    expect(isFormDisplayed).toBe(true);
  });

  test('should hide form when clicking Cancel', async () => {
    await settings.clickAddPathPairButton();
    
    expect(await settings.isPathPairFormDisplayed()).toBe(true);
    
    await settings.clickPathPairCancel();
    
    // Wait for form to be hidden by checking for empty state to appear
    await settings.page.waitForFunction(() => {
      const emptyState = document.querySelector('.empty-state, [class*="empty"]');
      const form = document.querySelector('form');
      return emptyState !== null || form === null;
    }, { timeout: 2000 });
    
    // After cancel, the empty state should be displayed instead of the form
    expect(await settings.isPathPairsEmptyStateDisplayed()).toBe(true);
  });

  test('should be able to fill path pair form fields', async () => {
    await settings.clickAddPathPairButton();
    
    await settings.fillPathPairForm('Test Movies', '/remote/movies', '/local/movies');
    
    // Verify fields are filled (by checking they don't throw)
    const nameField = settings.page.getByRole('textbox', { name: 'Name' });
    await expect(nameField).toHaveValue('Test Movies');
    
    const remoteField = settings.page.getByRole('textbox', { name: 'Remote Path *' });
    await expect(remoteField).toHaveValue('/remote/movies');
    
    const localField = settings.page.getByRole('textbox', { name: 'Local Path *' });
    await expect(localField).toHaveValue('/local/movies');
    
    // Cancel to clean up
    await settings.clickPathPairCancel();
  });

  test('should have Enabled checkbox checked by default', async () => {
    await settings.clickAddPathPairButton();
    
    const enabledCheckbox = settings.page.getByRole('checkbox', { name: 'Enabled' });
    await expect(enabledCheckbox).toBeChecked();
    
    await settings.clickPathPairCancel();
  });

  test('should have Auto-queue checkbox checked by default', async () => {
    await settings.clickAddPathPairButton();
    
    const autoQueueCheckbox = settings.page.getByRole('checkbox', { name: 'Auto-queue new files' });
    await expect(autoQueueCheckbox).toBeChecked();
    
    await settings.clickPathPairCancel();
  });
});

test.describe('Settings Page - Network Mounts', () => {
  let settings: SettingsPage;

  test.beforeEach(async ({ page }) => {
    settings = new SettingsPage(page);
    await settings.goto();
  });

  test('should have Add Network Mount button', async () => {
    const isPresent = await settings.isAddNetworkMountButtonPresent();
    expect(isPresent).toBe(true);
  });

  test('should show empty state when no network mounts configured', async () => {
    const isEmpty = await settings.isNetworkMountsEmptyStateDisplayed();
    expect(isEmpty).toBe(true);
  });
});
