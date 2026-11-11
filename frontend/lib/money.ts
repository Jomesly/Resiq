// Money is a decimal string ("1250.50") end to end. Arithmetic happens in integer centavos.

export function toCents(value: string | null | undefined): number | null {
  if (value == null) return null;
  const clean = String(value).replace(/[₱,\s]/g, "").replace(/^P/i, "");
  if (clean === "" || !/^-?\d+(\.\d{1,2})?$/.test(clean)) return null;
  const negative = clean.startsWith("-");
  const [whole, frac = ""] = clean.replace("-", "").split(".");
  const cents = Number(whole) * 100 + Number(frac.padEnd(2, "0"));
  if (!Number.isSafeInteger(cents)) return null;
  return negative ? -cents : cents;
}

export function centsToString(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
}

export function sumMoney(values: (string | null | undefined)[]): string {
  return centsToString(values.reduce<number>((sum, v) => sum + (toCents(v) ?? 0), 0));
}

const grouping = new Intl.NumberFormat("en-PH", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** "2000" → "2,000.00" (no currency sign), for ledger columns. */
export function formatAmount(value: string | null | undefined): string {
  const cents = toCents(value);
  if (cents == null) return "—";
  return (cents < 0 ? "-" : "") + grouping.format(Math.abs(cents) / 100);
}

export function formatPeso(value: string | null | undefined): string {
  const cents = toCents(value);
  if (cents == null) return "—";
  return (cents < 0 ? "-₱" : "₱") + grouping.format(Math.abs(cents) / 100);
}

/** "1,250.5" → "1250.50"; returns the input unchanged when it is not a number. */
export function normalizeMoney(value: string): string {
  const cents = toCents(value);
  return cents == null ? value : centsToString(cents);
}
