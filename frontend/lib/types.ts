// Mirrors the backend contract in the plan (Task 17). Money is always a decimal string.

export type ReceiptStatus = "queued" | "processing" | "needs_review" | "verified" | "failed";

/** x0, y0, x1, y1 in processed-image pixels. */
export type Box = [number, number, number, number];

export interface FieldValue<T> {
  value: T | null;
  confidence: number;
  source: string | null;
  box: Box | null;
}

export interface LineItemCandidate {
  description: string;
  quantity: string | null;
  unit_price: string | null;
  amount: string;
  confidence: number;
  box: Box;
}

export interface Check {
  name: "vat_math" | "items_sum" | "subtotal_vat_total";
  passed: boolean;
  detail: string;
}

export interface Extraction {
  merchant: FieldValue<string>;
  merchant_tin: FieldValue<string>;
  receipt_number: FieldValue<string>;
  receipt_date: FieldValue<string>;
  subtotal: FieldValue<string>;
  vatable_sales: FieldValue<string>;
  vat_amount: FieldValue<string>;
  vat_exempt: FieldValue<string>;
  total: FieldValue<string>;
  line_items: LineItemCandidate[];
  category: FieldValue<string>;
  checks: Check[];
  warnings: string[];
  engine_version: string;
}

export interface QualityReport {
  blur_score: number;
  is_blurry: boolean;
  brightness: number;
  is_dark: boolean;
  skew_angle: number;
  document_found: boolean;
  warnings: string[];
}

export interface LineItem {
  id?: string;
  position: number;
  description: string;
  quantity: string | null;
  unit_price: string | null;
  amount: string | null;
}

export interface ReceiptSummary {
  id: string;
  status: ReceiptStatus;
  merchant: string | null;
  receipt_number: string | null;
  receipt_date: string | null;
  total: string | null;
  category: string | null;
  thumbnail_url: string | null;
  created_at: string;
  error: string | null;
}

export interface OcrLine {
  text: string;
  confidence: number;
  box: Box;
}

export type StageName = "original" | "warped" | "enhanced";

export interface ReceiptDetail extends ReceiptSummary {
  merchant_tin: string | null;
  subtotal: string | null;
  vatable_sales: string | null;
  vat_amount: string | null;
  vat_exempt: string | null;
  line_items: LineItem[];
  extraction: Extraction | null;
  quality: QualityReport | null;
  ocr_lines: OcrLine[];
  image: { processed_url: string; original_url: string; width: number; height: number } | null;
  stages: Partial<Record<StageName, string>>;
  verified_at: string | null;
}

export type JournalEntry = Pick<ReceiptDetail, keyof ReceiptSummary | "merchant_tin" | "subtotal" | "vatable_sales" | "vat_amount" | "vat_exempt">;
export interface JournalList { items: JournalEntry[]; next_cursor: string | null }

export interface ReceiptUpdate {
  merchant: string | null;
  merchant_tin: string | null;
  receipt_number: string | null;
  receipt_date: string | null;
  category: string | null;
  subtotal: string | null;
  vatable_sales: string | null;
  vat_amount: string | null;
  vat_exempt: string | null;
  total: string | null;
  line_items: LineItem[];
}

export interface ReceiptList {
  items: ReceiptSummary[];
  next_cursor: string | null;
}

export interface ListFilters {
  status?: ReceiptStatus | "";
  month?: string;
  q?: string;
}

export interface MonthlySummary {
  month: string;
  total: string;
  vat_total: string;
  count: number;
  by_category: { category: string; total: string; count: number }[];
  by_day: { date: string; total: string }[];
}

export const CATEGORIES = [
  "Food & Drinks",
  "Groceries",
  "Transport",
  "Fuel",
  "Utilities",
  "Office Supplies",
  "Health",
  "Other",
] as const;
export type Category = (typeof CATEGORIES)[number];
