import { defineConfig, devices } from '@playwright/test'

/** E2E del panel: levanta `dogfood panel` sobre un `runs/` de prueba (e2e/preparar_runs.py) con la
 * SPA ya construida (`scripts/build-web.sh`). Puerto propio para no chocar con el panel real (7470). */
const PUERTO = Number(process.env.E2E_PUERTO ?? 7481)
const RUNS = process.env.E2E_RUNS ?? '/tmp/dogfood-e2e-runs'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://127.0.0.1:${PUERTO}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `rm -rf ${RUNS} && uv run python web/e2e/preparar_runs.py ${RUNS} && uv run dogfood panel --raiz ${RUNS} --host 127.0.0.1 --puerto ${PUERTO}`,
    cwd: '..',
    url: `http://127.0.0.1:${PUERTO}/ayuda`,
    reuseExistingServer: false,
    timeout: 60_000,
  },
})
