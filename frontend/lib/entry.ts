import { z } from "zod";
import { normalizeMoney, toCents } from "./money";
import { CATEGORIES, type ReceiptDetail, type ReceiptUpdate } from "./types";

export const amountFields = ["vatable_sales", "vat_amount", "vat_exempt", "subtotal", "total"] as const;
export const headFields = ["merchant", "merchant_tin", "receipt_number", "receipt_date", "category"] as const;
export type EntryField = (typeof amountFields)[number] | (typeof headFields)[number];
export const entryInputId = (receiptId: string, field: string) => "entry-" + receiptId + "-" + field;
export const fieldLabels: Record<EntryField, string> = {
  merchant: "Merchant", merchant_tin: "TIN", receipt_number: "OR no.", receipt_date: "Date", category: "Category",
  vatable_sales: "VATable sales", vat_amount: "VAT at 12%", vat_exempt: "VAT-exempt sales", subtotal: "Subtotal", total: "Total",
};

const text = z.string().nullable();
const required = (message: string) => text.refine((value) => !!value?.trim(), message);
const money = text.refine((value) => value === null || (/^-?\d+(\.\d{1,2})?$/.test(value) && toCents(value) !== null), "Enter an amount with up to two decimal places.");
const date = text.refine((value) => {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(value + "T00:00:00Z");
  return Number.isFinite(+parsed) && parsed.toISOString().slice(0, 10) === value;
}, "Enter a valid receipt date.");

const schema = z.object({
  merchant: required("Enter the merchant name."), merchant_tin: text, receipt_number: text, receipt_date: date,
  category: z.enum(CATEGORIES, { error: "Choose a category from the list." }).nullable(),
  vatable_sales: money, vat_amount: money, vat_exempt: money, subtotal: money,
  total: money.refine((value) => value !== null, "Enter the receipt total."),
  line_items: z.array(z.object({
    position: z.number(), id: z.string().optional(),
    description: z.string().trim().min(1, "Enter a description."),
    quantity: text.refine((value) => value === null || /^\d+(\.\d{1,4})?$/.test(value), "Enter a valid quantity."),
    unit_price: money, amount: money.refine((value) => value !== null, "Enter the line amount."),
  })),
});

export function entryFromReceipt(detail: ReceiptDetail): ReceiptUpdate {
  const { merchant, merchant_tin, receipt_number, receipt_date, category, subtotal, vatable_sales, vat_amount, vat_exempt, total, line_items } = detail;
  return { merchant, merchant_tin, receipt_number, receipt_date, category, subtotal, vatable_sales, vat_amount, vat_exempt, total, line_items };
}

const clean = (value: string | null) => value?.trim() || null;
const cleanMoney = (value: string | null) => {
  const trimmed = clean(value);
  return trimmed === null ? null : normalizeMoney(trimmed);
};

export function validateEntry(entry: ReceiptUpdate) {
  return schema.safeParse({
    ...Object.fromEntries(headFields.map((field) => [field, clean(entry[field])])),
    ...Object.fromEntries(amountFields.map((field) => [field, cleanMoney(entry[field])])),
    line_items: entry.line_items.map((item, position) => ({
      ...item, position, quantity: clean(item.quantity), amount: cleanMoney(item.amount), unit_price: cleanMoney(item.unit_price),
    })),
  });
}
