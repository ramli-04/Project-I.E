import { defineConfig } from '@playwright/test';

// Refuse mixed demo/verification targets before any live test can create data.
const frontend = process.env.VIRTUAL_LAB_FRONTEND || 'http://localhost:18080';
const backend = process.env.VIRTUAL_LAB_BACKEND || 'http://127.0.0.1:18000';
const project = process.env.VIRTUAL_LAB_PROJECT || 'cabinet-virtual-lab';
const targets = { '18080': ['18000', 'cabinet-virtual-lab'], '18081': ['18001', 'cabinet-ui-verification'] };
const expected = targets[new URL(frontend).port];
if (expected && (new URL(backend).port !== expected[0] || project !== expected[1])) {
  throw new Error('Live test targets disagree: set VIRTUAL_LAB_FRONTEND, VIRTUAL_LAB_BACKEND and VIRTUAL_LAB_PROJECT to the same Docker environment.');
}

export default defineConfig({
  testDir: './tests', testMatch: '**/*.live.spec.js', workers: 1,
  timeout: 90000, expect: { timeout: 15000 },
  outputDir: '../.runtime/live-browser-results',
  reporter: [['list'], ['html', { outputFolder: '../.runtime/live-browser-report', open: 'never' }]],
  use: {
    baseURL: process.env.VIRTUAL_LAB_FRONTEND || 'http://localhost:18080', headless: true,
    viewport: { width: 1440, height: 1000 }, screenshot: 'only-on-failure',
    launchOptions: { args: ['--host-resolver-rules=MAP simlab.localhost 127.0.0.1'] },
  },
});
