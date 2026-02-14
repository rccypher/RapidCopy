import { test, expect } from '@playwright/test';
import { AutoQueuePage } from './pages/autoqueue.page';

test.describe('AutoQueue Page - UI Elements', () => {
  let autoqueue: AutoQueuePage;

  test.beforeEach(async ({ page }) => {
    autoqueue = new AutoQueuePage(page);
    await autoqueue.goto();
  });

  test('should have correct top title', async () => {
    const title = await autoqueue.getTopTitle();
    expect(title).toBe('AutoQueue');
  });

  test('should have add pattern input visible', async () => {
    const isVisible = await autoqueue.isAddPatternInputVisible();
    expect(isVisible).toBe(true);
  });
});

/**
 * AutoQueue tests that require backend connection
 * These tests are skipped by default - run with: npx playwright test --grep @backend
 */
test.describe('AutoQueue Page - Pattern Management', () => {
  let autoqueue: AutoQueuePage;

  // Skip all tests in this describe block - they require backend
  test.skip(({ }, testInfo) => true, 'AutoQueue pattern tests require backend connection');

  test.beforeEach(async ({ page }) => {
    autoqueue = new AutoQueuePage(page);
    await autoqueue.goto();
  });

  test('should add and remove patterns @backend', async () => {
    // Start with empty or existing list
    const initialPatterns = await autoqueue.getPatterns();
    const initialCount = initialPatterns.length;

    // Add patterns
    await autoqueue.addPattern('APattern');
    await autoqueue.addPattern('CPattern');
    await autoqueue.addPattern('DPattern');
    await autoqueue.addPattern('BPattern');

    let patterns = await autoqueue.getPatterns();
    expect(patterns.length).toBe(initialCount + 4);
    expect(patterns.slice(-4)).toEqual(['APattern', 'CPattern', 'DPattern', 'BPattern']);

    // Remove patterns one by one (from the newly added ones)
    const startIndex = initialCount;
    await autoqueue.removePattern(startIndex + 2); // Remove DPattern
    patterns = await autoqueue.getPatterns();
    expect(patterns.slice(startIndex)).toEqual(['APattern', 'CPattern', 'BPattern']);

    await autoqueue.removePattern(startIndex); // Remove APattern
    patterns = await autoqueue.getPatterns();
    expect(patterns.slice(startIndex)).toEqual(['CPattern', 'BPattern']);

    await autoqueue.removePattern(startIndex + 1); // Remove BPattern
    patterns = await autoqueue.getPatterns();
    expect(patterns.slice(startIndex)).toEqual(['CPattern']);

    await autoqueue.removePattern(startIndex); // Remove CPattern
    patterns = await autoqueue.getPatterns();
    expect(patterns.length).toBe(initialCount);
  });

  test('should persist patterns in alphabetical order after reload @backend', async ({ page }) => {
    // Clean start - get initial patterns
    const initialPatterns = await autoqueue.getPatterns();

    // Add patterns in non-alphabetical order
    await autoqueue.addPattern('ZPattern');
    await autoqueue.addPattern('APattern');
    await autoqueue.addPattern('MPattern');

    // Reload the page
    await autoqueue.goto();

    // Patterns should be in alphabetical order
    const reloadedPatterns = await autoqueue.getPatterns();
    const newPatterns = reloadedPatterns.filter(p => !initialPatterns.includes(p));
    
    // New patterns should be sorted alphabetically
    const sortedNew = [...newPatterns].sort();
    expect(newPatterns).toEqual(sortedNew);

    // Clean up - remove the added patterns
    for (const pattern of newPatterns) {
      const currentPatterns = await autoqueue.getPatterns();
      const index = currentPatterns.indexOf(pattern);
      if (index >= 0) {
        await autoqueue.removePattern(index);
      }
    }
  });
});
