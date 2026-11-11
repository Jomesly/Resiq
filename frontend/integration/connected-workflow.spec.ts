import { readFile } from "node:fs/promises";
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("real photo travels through OCR, review, PostgreSQL, journal and CSV", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/upload");
  // A different filename proves this is pixel-based OCR, not the demo sample lookup.
  await page.locator("input[type=file]").setInputFiles({ name: "phone-photo.png", mimeType: "image/png", buffer: await readFile("public/samples/kapihan.png") });
  await page.getByRole("link", { name: "Open phone-photo.png" }).click();
  await expect(page.locator("[data-entry-field=total]:visible")).toHaveValue("145.00", { timeout: 120_000 });
  await expect(page.getByRole("img", { name: /Receipt from/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Focus Total" })).toBeVisible();
  const receiptUrl = page.url();
  await page.getByLabel("Merchant", { exact: true }).fill("Connected OCR evaluation");
  await page.getByLabel("Date", { exact: true }).fill("2026-11-09");
  await page.locator("[data-entry-field=total]:visible").fill("135.00");
  await expect(page.getByText(/Some amounts do not reconcile/)).toHaveCount(0);
  for (const width of [320, 375, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
  }
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.getByRole("button", { name: "Save to journal" }).click();
  await expect(page.getByRole("heading", { name: "Saved to November" })).toBeVisible();
  await page.getByRole("link", { name: "Open journal" }).click();
  await expect(page.getByRole("link", { name: "Connected OCR evaluation" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("link", { name: "Connected OCR evaluation" })).toBeVisible();
  const downloading = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export November as CSV" }).click();
  const download = await downloading;
  expect(await readFile(await download.path(), "utf8")).toContain("Connected OCR evaluation");
  await page.goto(receiptUrl);
  await page.getByRole("button", { name: "Read again" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Read again" }).click();
  await expect(page.locator("[data-entry-field=total]:visible")).toHaveValue("145.00", { timeout: 120_000 });
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await page.getByRole("button", { name: "Delete receipt" }).click();
  await expect(page.getByRole("heading", { name: "No receipts yet." })).toBeVisible();
  expect(errors).toEqual([]);
});

test("sideways phone image uses upright processed pixels for source overlays", async ({ page }) => {
  await page.goto("/upload");
  await page.locator("input[type=file]").setInputFiles("integration/fixtures/sideways.png");
  await page.getByRole("link", { name: "Open sideways.png" }).click();
  await expect(page.locator("[data-entry-field=total]:visible")).toHaveValue("145.00", { timeout: 120_000 });
  const photo = page.getByRole("img", { name: /Receipt from/ });
  await expect(photo).toHaveAttribute("src", /\/processed\?/);
  await expect.poll(() => photo.evaluate((image: HTMLImageElement) => image.complete && image.naturalHeight > image.naturalWidth)).toBe(true);
  await page.getByRole("button", { name: "Focus Total" }).click();
  await expect(page.locator("[data-entry-field=total]:visible")).toBeFocused();
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await page.getByRole("button", { name: "Delete receipt" }).click();
  await expect(page.getByRole("heading", { name: "No receipts yet." })).toBeVisible();
});
