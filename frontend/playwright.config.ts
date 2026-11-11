import { defineConfig, devices } from "@playwright/test";

const baseURL = "http://localhost:3000";

export default defineConfig({
  outputDir: "test-results/demo",
  testDir: "./e2e",
  use: { ...devices["Desktop Chrome"], baseURL, trace: "retain-on-failure" },
  webServer: {
    command: "npm run dev",
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 90_000,
    env: { NEXT_PUBLIC_DEMO_MODE: "true", NEXT_PUBLIC_API_URL: "" },
  },
});
