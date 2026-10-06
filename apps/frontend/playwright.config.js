import { defineConfig } from '@playwright/test';

const managedApi = process.env.REPORTER_E2E_MANAGED_API === '1';
if (managedApi) {
  process.env.REPORTER_LIVE_API = 'http://127.0.0.1:8011';
  process.env.REPORTER_STUDIO_TEST_API = 'http://127.0.0.1:8011';
}

export default defineConfig({
  testDir: './e2e',
  globalTeardown: './e2e/global-teardown.js',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: 'node scripts/start-test-server.mjs',
      url: 'http://127.0.0.1:4173',
      reuseExistingServer: !process.env.CI && !managedApi,
      timeout: 120000,
    },
    ...(managedApi
      ? [
          {
            command: `"${process.env.REPORTER_TEST_PYTHON || 'python'}" ../../scripts/serve_studio_test_backend.py`,
            url: 'http://127.0.0.1:8011/api/health',
            reuseExistingServer: false,
            timeout: 120000,
          },
        ]
      : []),
  ],
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
});
