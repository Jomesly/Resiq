import { centsToString, formatPeso, toCents } from "./money";
import type { Check, ReceiptUpdate } from "./types";

type Amounts = Pick<ReceiptUpdate, "vatable_sales" | "vat_amount" | "vat_exempt" | "subtotal" | "total" | "line_items">;

export function liveChecks(values: Amounts): Check[] {
  const sales = toCents(values.vatable_sales);
  const vat = toCents(values.vat_amount);
  const exempt = toCents(values.vat_exempt);
  const total = toCents(values.total);
  const subtotal = toCents(values.subtotal);
  const items = values.line_items.map((item) => toCents(item.amount));
  const checks: Check[] = [];
  const peso = (cents: number) => formatPeso(centsToString(cents));

  if (sales !== null && vat !== null) {
    const passed = Math.abs(sales * 12 - vat * 100) <= 200;
    checks.push({ name: "vat_math", passed, detail: passed ? "VAT is 12% of VATable sales." : `VAT should be ${peso(Math.round(sales * 12 / 100))}; the entry says ${peso(vat)}.` });
  }
  if (total !== null && ((sales !== null && vat !== null) || (sales === null && vat === null && exempt !== null))) {
    const sum = (sales ?? 0) + (vat ?? 0) + (exempt ?? 0);
    const difference = Math.abs(sum - total);
    const passed = difference <= 5;
    checks.push({ name: "subtotal_vat_total", passed, detail: passed ? "The VAT breakdown adds to the total." : `Does not balance by ${peso(difference)}. The VAT lines add to ${peso(sum)}; the total says ${peso(total)}.` });
  }
  const expected = subtotal ?? total;
  if (expected !== null && items.length && items.every((item) => item !== null)) {
    const sum = items.reduce<number>((a, b) => a + (b ?? 0), 0);
    const difference = Math.abs(sum - expected);
    const passed = difference <= 5;
    checks.push({ name: "items_sum", passed, detail: passed ? `Line items add to the ${subtotal === null ? "total" : "subtotal"}.` : `Line items differ by ${peso(difference)}. They add to ${peso(sum)}; the ${subtotal === null ? "total" : "subtotal"} says ${peso(expected)}.` });
  }
  return checks;
}

export function isBalanced(values: Amounts, checks = liveChecks(values)) {
  const invalidAmount = [values.subtotal, values.total, values.vatable_sales, values.vat_amount, values.vat_exempt, ...values.line_items.map((item) => item.amount)].some((value) => value?.trim() && toCents(value) === null);
  const total = toCents(values.total);
  const subtotal = toCents(values.subtotal);
  return !invalidAmount && total !== null && values.line_items.every((item) => toCents(item.amount) !== null) &&
    checks.some((check) => check.name === "subtotal_vat_total" || (check.name === "items_sum" && (subtotal === null || Math.abs(subtotal - total) <= 5))) &&
    checks.every((check) => check.passed);
}
