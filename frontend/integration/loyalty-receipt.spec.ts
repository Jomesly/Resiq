import { expect, test } from "@playwright/test";

// Optional private-image check. The user's receipt is never bundled into public assets.
test("ignores the Go Rewards points block on a real supermarket receipt", async ({ page }) => {
  const image = process.env.RESIQ_LOYALTY_TEST_IMAGE;
  test.skip(!image, "Set RESIQ_LOYALTY_TEST_IMAGE to the diagnosed receipt photo.");
  await page.goto("/upload");
  await page.locator("input[type=file]").setInputFiles(image!);
  await page.getByRole("link", { name: /^Open / }).click();
  await expect(page.locator("[data-entry-field=total]:visible")).toHaveValue("62.00", { timeout: 120_000 });
  for (const [field, value] of Object.entries({
    merchant_tin: "000-405-340-020", receipt_number: "0000098076", receipt_date: "2024-02-01",
    vatable_sales: "55.36", vat_amount: "6.64", vat_exempt: "0.00",
  })) await expect(page.locator(`[data-entry-field=${field}]:visible`)).toHaveValue(value);
  await expect(page.getByLabel("Particulars, line 1")).toHaveValue("CHARMEE AN LONG 10S");
  await expect(page.getByLabel("Amount, line 1")).toHaveValue("62.00");
  await expect(page.getByLabel("Particulars, line 2")).toHaveCount(0);
  await expect(page.getByText("Balanced.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await page.getByRole("button", { name: "Delete receipt" }).click();
  await expect(page.getByRole("heading", { name: "No receipts yet." })).toBeVisible();
});
