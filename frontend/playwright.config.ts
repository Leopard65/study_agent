import { defineConfig, devices } from '@playwright/test';

const backendPort = Number(process.env.E2E_BACKEND_PORT || 18000);
const frontendPort = Number(process.env.E2E_FRONTEND_PORT || 15173);
const isWindows = process.platform === 'win32';

const backendCommand = isWindows
  ? `cd ..\\backend && .venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port ${backendPort}`
  : `cd ../backend && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port ${backendPort}`;

export default defineConfig({
  testDir: './e2e',
  outputDir: './test-results',
  timeout: 30_000,
  expect: { timeout: 8_000 },
  fullyParallel: false,
  reporter: [
    ['list'],
    ['html', { open: 'never' }],
  ],
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: backendCommand,
      url: `http://127.0.0.1:${backendPort}/api/health`,
      reuseExistingServer: false,
      timeout: 30_000,
      env: {
        DATABASE_URL: 'sqlite+aiosqlite:///./data/e2e.db',
        UPLOAD_DIR: './uploads/e2e',
        OPENAI_API_KEY: '',
        OCR_ENABLED: 'false',
        CORS_ORIGINS: `http://127.0.0.1:${frontendPort}`,
      },
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${frontendPort}`,
      url: `http://127.0.0.1:${frontendPort}`,
      reuseExistingServer: false,
      timeout: 30_000,
      env: {
        VITE_API_TARGET: `http://127.0.0.1:${backendPort}`,
      },
    },
  ],
});
