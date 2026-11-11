import { describe, expect, it } from "vitest";
import { isBalanced, liveChecks } from "@/lib/checks";
import type { ReceiptUpdate } from "@/lib/types";

const entry: ReceiptUpdate = {
  merchant: "Kapihan sa Kanto", merchant_tin: null, receipt_number: null, receipt_date: "2026-11-09", category: null,
  subtotal: null, vatable_sales: "120.54", vat_amount: "14.46", vat_exempt: null, total: "145.00",
  line_items: [
    { position: 0, description: "Coffee", quantity: "2", unit_price: "45.00", amount: "90.00" },
    { position: 1, description: "Ensaymada", quantity: null, unit_price: null, amount: "45.00" },
  ],
};

describe("receipt reconciliation", () => {
  it("finds the ₱10 mismatch and clears it when the total is corrected", () => {
    expect(liveChecks(entry).find((check) => check.name === "subtotal_vat_total")).toMatchObject({
      passed: false, detail: expect.stringContaining("₱10.00"),
    });
    expect(isBalanced(entry)).toBe(false);
    expect(isBalanced({ ...entry, total: "135.00" })).toBe(true);
  });

  it("does not call an uncheckable or invalid entry balanced", () => {
    expect(isBalanced({ ...entry, line_items: [], total: "135.00", vatable_sales: null, vat_amount: null })).toBe(false);
    expect(isBalanced({ ...entry, total: "135.00", vat_exempt: "oops" })).toBe(false);
  });

  it("accepts rounding within five centavos and flags anything beyond it", () => {
    expect(isBalanced({ ...entry, total: "135.05" })).toBe(true);
    expect(isBalanced({ ...entry, total: "135.06" })).toBe(false);
  });
});
