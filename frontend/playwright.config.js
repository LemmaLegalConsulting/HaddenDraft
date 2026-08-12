import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
  outputDir: "test-results",
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: process.env.E2E_BASE_URL ? undefined : [
    {
      command: ".venv/bin/python backend/manage.py runserver 127.0.0.1:8000",
      cwd: "..",
      url: "http://127.0.0.1:8000/api/bootstrap/",
      reuseExistingServer: true,
      timeout: 120_000,
      env: {
        LEGALSERVER_ALLOW_WRITES: process.env.E2E_ALLOW_LEGALSERVER_WRITES === "1" ? "true" : "false",
        AI_DRAFTING_ENABLED: "false",
      },
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5173",
      url: "http://127.0.0.1:5173/",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
