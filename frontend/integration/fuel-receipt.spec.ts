import { expect, test } from "@playwright/test";

// Optional private-image check. The user's receipt is never bundled into public assets.
test("extracts the real fuel receipt's VAT, date and quantity", async ({ page }) => {
  const image = process.env.RESIQ_PETRON_TEST_IMAGE;
  test.skip(!image, "Set RESIQ_PETRON_TEST_IMAGE to the diagnosed receipt photo.");
  await page.goto("/upload");
  await page.locator("input[type=file]").setInputFiles(image!);
  await page.getByRole("link", { name: /^Open / }).click();
  await expect(page.locator("[data-entry-field=total]:visible")).toHaveValue("200.00", { timeout: 120_000 });
  for (const [field, value] of Object.entries({
    merchant: "ROLLINGHILLS GASOLINE STATION", merchant_tin: "131-154-330-000",
    receipt_number: "514700", receipt_date: "2015-02-04", vatable_sales: "178.57",
    vat_amount: "21.43", vat_exempt: "0.00",
  })) await expect(page.locator(`[data-entry-field=${field}]:visible`)).toHaveValue(value);
  await expect(page.getByRole("combobox", { name: /Category/ })).toHaveValue("Fuel");
  await expect(page.getByLabel("Qty, line 1")).toHaveValue("6.3291");
  await expect(page.getByLabel("Unit price, line 1")).toHaveValue("31.60");
  await expect(page.getByText(/older than 10 years/)).toBeVisible();
  await expect(page.getByText("Balanced.", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.locator("[data-entry-field=vat_amount]:visible")).toHaveValue("21.43");
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await page.getByRole("button", { name: "Delete receipt" }).click();
  await expect(page.getByRole("heading", { name: "No receipts yet." })).toBeVisible();
});
