import { sumMoney } from "./money";
import type { MonthlySummary, ReceiptDetail } from "./types";

export const csvHeader = "date,merchant,tin,receipt_number,category,vatable_sales,vat_amount,vat_exempt,total,status";

function cell(value: string | null) {
  if (!value) return "";
  const literal = /^[\s]*[=+\-@\t\r]/.test(value) && !/^-\d+(\.\d{1,2})?$/.test(value) ? `'${value}` : value;
  return /[",\r\n]/.test(literal) ? `"${literal.replaceAll('"', '""')}"` : literal;
}

export function receiptCsv(rows: ReceiptDetail[]) {
  return [csvHeader, ...rows.map((row) => [row.receipt_date, row.merchant, row.merchant_tin, row.receipt_number, row.category, row.vatable_sales, row.vat_amount, row.vat_exempt, row.total, row.status].map(cell).join(","))].join("\r\n") + "\r\n";
}

export function saveCsv(filename: string, csv: string) {
  const href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 1000);
}

export function summarize(month: string, rows: ReceiptDetail[]): MonthlySummary {
  const groups = new Map<string, ReceiptDetail[]>();
  const days = new Map<string, ReceiptDetail[]>();
  for (const row of rows) {
    const category = row.category || "Other";
    groups.set(category, [...(groups.get(category) ?? []), row]);
    if (row.receipt_date) days.set(row.receipt_date, [...(days.get(row.receipt_date) ?? []), row]);
  }
  const total = (group: ReceiptDetail[]) => sumMoney(group.map((row) => row.total));
  return {
    month, count: rows.length, total: total(rows), vat_total: sumMoney(rows.map((row) => row.vat_amount)),
    by_category: [...groups].map(([category, group]) => ({ category, total: total(group), count: group.length })).sort((a, b) => Number(b.total) - Number(a.total)),
    by_day: [...days].map(([date, group]) => ({ date, total: total(group) })).sort((a, b) => a.date.localeCompare(b.date)),
  };
}
