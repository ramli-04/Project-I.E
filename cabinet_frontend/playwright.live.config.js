import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests', testMatch: '**/*.live.spec.js', workers: 1,
  timeout: 90000, expect: { timeout: 15000 },
  outputDir: '../.runtime/live-browser-results',
  reporter: [['list'], ['html', { outputFolder: '../.runtime/live-browser-report', open: 'never' }]],
  use: {
    baseURL: 'http://localhost:18080', headless: true,
    viewport: { width: 1440, height: 1000 }, screenshot: 'only-on-failure',
    launchOptions: { args: ['--host-resolver-rules=MAP simlab.localhost 127.0.0.1'] },
  },
});
