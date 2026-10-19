import { defineConfig, devices } from '@playwright/test'

const isCI = Boolean(process.env.CI)

// Corre contra un stack ya levantado (./setup.sh): no arranca ningún servidor.
export default defineConfig({
  testDir: './tests',
  forbidOnly: isCI,
  retries: isCI ? 1 : 0,
  reporter: isCI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: process.env.DROIDESK_BASE_URL ?? 'http://localhost:8080',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
