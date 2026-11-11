import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  outputDir: "test-results/connected",
  testDir: "./integration", timeout: 180_000,
  use: { ...devices["Desktop Chrome"], baseURL: process.env.INTEGRATION_UI_URL || "http://localhost:3001", trace: "retain-on-failure" },
});
