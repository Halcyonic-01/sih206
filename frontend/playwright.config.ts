import {defineConfig} from '@playwright/test';

const ci = !!process.env.CI;

export default defineConfig({
  testDir: './tests', workers: 1, timeout: 90000, retries: ci ? 1 : 0,
  outputDir: process.env.PLAYWRIGHT_OUTPUT_DIR || (ci ? 'test-results' : '../planning/browser-results'),
  reporter: ci ? [['list'], ['html', {open: 'never', outputFolder: 'playwright-report'}]] : 'list',
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || process.env.PORTAL_URL || 'http://127.0.0.1:8010',
    viewport: {width: 1440, height: 1000},
    trace: ci ? 'retain-on-failure' : 'off',
    screenshot: ci ? 'only-on-failure' : 'off',
    // Optional: run against an already installed Chromium instead of the one Playwright downloads.
    launchOptions: {executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH || undefined},
  },
});
