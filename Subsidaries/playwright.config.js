const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './e2e',
  timeout: 240000,
  expect: { timeout: 120000 },
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5000',
    browserName: 'chromium',
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'python e2e/test_server.py',
    url: 'http://127.0.0.1:5000/workflow',
    reuseExistingServer: false,
    timeout: 120000,
    env: { IPMPRS_DEMO_PASSWORD: 'demo123' },
  },
});