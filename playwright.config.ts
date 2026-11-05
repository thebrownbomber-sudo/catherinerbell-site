import { defineConfig, devices } from "@playwright/test";

// Two modes:
//  - Default (CI on every PR): serves the freshly built _site/ folder locally
//    and runs the full suite against it.
//  - BASE_URL set (after a deploy): runs only the read-only @smoke tests
//    against the live site. Nothing is submitted to real forms.
const liveUrl = process.env.BASE_URL;
const port = 4173;

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 30_000,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: liveUrl ?? `http://127.0.0.1:${port}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop-chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile-chromium", use: { ...devices["Pixel 7"] } },
  ],
  webServer: liveUrl
    ? undefined
    : {
        command: `python3 -m http.server ${port} --bind 127.0.0.1 --directory _site`,
        url: `http://127.0.0.1:${port}/`,
        reuseExistingServer: !process.env.CI,
        timeout: 30_000,
      },
});
