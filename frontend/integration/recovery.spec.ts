import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("saved recovery code restores the same workspace after browser storage loss", async ({ page }) => {
  await page.goto("/workspace");
  await page.getByRole("button", { name: "Create recovery code", exact: true }).click();
  const code = await page.getByLabel("Your new recovery code").inputValue();
  expect(code.length).toBeGreaterThanOrEqual(43);
  await expect(page.getByRole("button", { name: "Enable saved code" })).toBeDisabled();
  await page.getByLabel("I saved this code outside this browser.").check();
  await page.getByRole("button", { name: "Enable saved code" }).click();
  await expect(page.getByText("Recovery is enabled. Keep your saved code safe.")).toBeVisible();
  for (const width of [320, 375, 1024]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
  }
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  const stored = await page.evaluate(() => Object.entries(localStorage).find(([key]) => key.startsWith("resiq.token:"))!);
  const base = stored[0].slice("resiq.token:".length);
  const photo = await page.request.get("/samples/kapihan.png");
  const uploaded = await page.request.post(base + "/api/receipts", { headers: { authorization: "Bearer " + stored[1] }, multipart: { file: { name: "recovery-check.png", mimeType: "image/png", buffer: await photo.body() } } });
  expect(uploaded.status()).toBe(202);
  const id = (await uploaded.json()).id;
  try {
    await page.evaluate(() => localStorage.clear());
    await page.reload();
    await page.getByLabel("Saved recovery code", { exact: true }).fill(code);
    await page.getByRole("button", { name: "Recover and sign out other devices" }).click();
    await expect(page).toHaveURL(/\/receipts$/);
    await expect(page.locator(`a[href='/receipts/${id}']`).first()).toBeVisible();
    expect((await page.request.get(base + "/api/receipts", { headers: { authorization: "Bearer " + stored[1] } })).status()).toBe(401);
  } finally {
    const token = await page.evaluate((key) => localStorage.getItem(key), stored[0]);
    if (token) await page.request.delete(base + "/api/receipts/" + id, { headers: { authorization: "Bearer " + token } });
  }
});
