import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for RapidCopy E2E tests
 * 
 * @see https://playwright.dev/docs/test-configuration
 * 
 * Test Projects:
 * - ui-only: Tests that don't require backend (default)
 * - with-backend: Tests that require the RapidCopy backend to be running
 * 
 * Run commands:
 *   npx playwright test                        # Run ui-only tests
 *   npx playwright test --project=ui-only      # Run ui-only tests explicitly
 *   npx playwright test --project=with-backend # Run backend-dependent tests
 *   npx playwright test --project=all          # Run all tests (requires backend)
 */
export default defineConfig({
  testDir: './tests',
  
  /* Run tests in files in parallel */
  fullyParallel: true,
  
  /* Fail the build on CI if you accidentally left test.only in the source code */
  forbidOnly: !!process.env.CI,
  
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  
  /* Opt out of parallel tests on CI */
  workers: process.env.CI ? 1 : undefined,
  
  /* Reporter to use */
  reporter: [
    ['html', { open: 'never' }],
    ['list']
  ],
  
  /* Shared settings for all the projects below */
  use: {
    /* Base URL - can be overridden with RAPIDCOPY_URL env var */
    baseURL: process.env.RAPIDCOPY_URL || 'http://localhost:8800',

    /* Collect trace when retrying the failed test */
    trace: 'on-first-retry',
    
    /* Screenshot on failure */
    screenshot: 'only-on-failure',
    
    /* Video on failure */
    video: 'on-first-retry',
  },

  /* Configure projects for different test scenarios */
  projects: [
    {
      name: 'ui-only',
      use: { ...devices['Desktop Chrome'] },
      // Only run tests NOT tagged with @backend
      grepInvert: /@backend/,
    },
    {
      name: 'with-backend',
      use: { ...devices['Desktop Chrome'] },
      // Only run tests tagged with @backend
      grep: /@backend/,
    },
    {
      name: 'all',
      use: { ...devices['Desktop Chrome'] },
      // Run all tests
    },
    // Uncomment to test on other browsers
    // {
    //   name: 'firefox',
    //   use: { ...devices['Desktop Firefox'] },
    // },
    // {
    //   name: 'webkit',
    //   use: { ...devices['Desktop Safari'] },
    // },
  ],

  /* Timeout for each test */
  timeout: 30000,
  
  /* Timeout for each expect assertion */
  expect: {
    timeout: 5000,
  },

  /* Run your local dev server before starting the tests */
  // webServer: {
  //   command: 'docker-compose -f ../../docker-compose.qa.yml up',
  //   url: 'http://localhost:8800',
  //   reuseExistingServer: !process.env.CI,
  //   timeout: 120000,
  // },
});
