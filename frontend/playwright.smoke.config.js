import { defineConfig } from "@playwright/test";

// The screen smoke check, separated from the credentialed e2e matrix so it can
// run on every push. It stubs the API in the browser, so it needs no Django, no
// database and no LegalServer login -- only the built app on a static server,
// which is what production actually serves.
export default defineConfig({
  testDir: "./e2e",
  testMatch: /screens-render\.spec\.js/,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: [["list"], ["html", { outputFolder: "playwright-report-smoke", open: "never" }]],
  outputDir: "test-results-smoke",
  use: {
    baseURL: process.env.SMOKE_BASE_URL || "http://127.0.0.1:4173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: process.env.SMOKE_BASE_URL ? undefined : {
    // The production build, not the dev server: a screen has to render in the
    // bundle that ships, and the two do not fail identically.
    command: "npm run build && npm run preview -- --host 127.0.0.1 --port 4173",
    url: "http://127.0.0.1:4173/",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
