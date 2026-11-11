// Captures the README screenshots from a running Resiq (frontend + API + OCR worker).
// Uses only the bundled synthetic sample receipts, in a fresh anonymous workspace.
// Usage: node scripts/capture-readme.mjs [baseUrl]   (default http://localhost:3000)
import { chromium } from "@playwright/test";

const base = process.argv[2] ?? "http://localhost:3000";
const out = (name) => `../docs/screenshots/${name}.png`;
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5 });
const page = await context.newPage();
page.setDefaultTimeout(120_000);

await page.goto(`${base}/`);
await page.getByRole("heading", { name: "From resibo to columnar book." }).waitFor();
await page.waitForTimeout(800);
await page.screenshot({ path: out("01-landing") });

// Upload two samples and let the OCR worker read them.
await page.goto(`${base}/upload`);
await page.locator("input[type=file]").setInputFiles(["public/samples/mercury.png", "public/samples/petron.png"]);
const openLinks = page.getByRole("link", { name: /^Open / });
await openLinks.nth(1).waitFor();
await page.getByText(/Needs review|Ready|Verified/).nth(1).waitFor();
await page.waitForTimeout(500);
await page.screenshot({ path: out("02-upload") });
const uploaded = await openLinks.evaluateAll((links) => links.map((a) => a.href));

// The misread sample: Resiq refuses to balance until the total is corrected.
await page.goto(`${base}/`);
await page.getByRole("button", { name: "Try a sample receipt" }).click();
await page.getByRole("heading", { name: "Kapihan sa Kanto" }).waitFor();
await page.getByText("Does not balance by ₱10.00.", { exact: true }).waitFor();
await page.getByRole("button", { name: "Focus Total" }).click();
await page.evaluate(() => window.scrollTo(0, 0));
await page.waitForTimeout(400);
await page.screenshot({ path: out("03-review-mismatch") });

const total = page.locator("[data-entry-field=total]:visible");
await total.fill("135");
await total.press("Tab");
await page.getByText("Ready to save").waitFor();
await page.getByRole("button", { name: "Focus Total" }).click();
await page.evaluate(() => window.scrollTo(0, 0));
await page.waitForTimeout(400);
await page.screenshot({ path: out("04-review-balanced") });

await page.setViewportSize({ width: 390, height: 844 });
await page.evaluate(() => window.scrollTo(0, 0));
await page.waitForTimeout(500);
await page.screenshot({ path: out("07-mobile-review") });
await page.setViewportSize({ width: 1440, height: 900 });

await page.getByRole("button", { name: "Save to journal" }).click();
await page.getByRole("heading", { name: /Saved to/ }).waitFor();

for (const href of uploaded) {
  await page.goto(href);
  const save = page.getByRole("button", { name: "Save to journal" });
  await save.waitFor();
  await save.click();
  await page.getByRole("heading", { name: /Saved to/ }).waitFor({ timeout: 15_000 }).catch(() => {});
}

await page.goto(`${base}/receipts`);
await page.getByRole("link", { name: "Kapihan sa Kanto" }).first().waitFor();
await page.waitForTimeout(500);
await page.screenshot({ path: out("05-receipts") });

await page.goto(`${base}/journal?month=2026-11`);
await page.getByRole("link", { name: "Kapihan sa Kanto" }).waitFor();
await page.waitForTimeout(800);
await page.screenshot({ path: out("06-journal"), fullPage: true });

await browser.close();
console.log("saved screenshots to docs/screenshots");
