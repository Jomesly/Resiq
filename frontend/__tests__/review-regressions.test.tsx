import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { ReceiptViewer } from "@/components/receipt-viewer";
import { ReceiptForm } from "@/components/receipt-form";
import type { Extraction, ReceiptDetail } from "@/lib/types";

function fixture(): ReceiptDetail {
  const empty = { value: null, confidence: 0, source: null, box: null };
  const extraction: Extraction = { merchant: empty, merchant_tin: empty, receipt_number: empty, receipt_date: empty, subtotal: empty, vatable_sales: empty, vat_amount: empty, vat_exempt: empty, total: empty, category: empty, line_items: [], checks: [], warnings: ["Some amounts do not reconcile. Check the photo before saving.", "Could not identify merchant. Please enter it."], engine_version: "paddle" };
  return { id: "test", status: "needs_review", merchant: null, receipt_number: null, receipt_date: "2026-11-09", total: "145.00", category: null, thumbnail_url: null, created_at: "2026-11-09T00:00:00Z", error: null, merchant_tin: null, subtotal: null, vatable_sales: "120.54", vat_amount: "14.46", vat_exempt: null, line_items: [], extraction, quality: null, ocr_lines: [], image: { original_url: "https://api.test/original", processed_url: "https://api.test/upright", width: 400, height: 800 }, stages: { original: "https://api.test/original", enhanced: "https://api.test/sideways" }, verified_at: null };
}

test("Read overlays use the upright OCR image, not the earlier enhanced stage", () => {
  const { container } = render(<ReceiptViewer detail={fixture()} boxes={[{ id: "total", label: "Total", box: [20, 300, 350, 330] }]} activeId={null} onBoxClick={vi.fn()} />);
  expect(screen.getByRole("img")).toHaveAttribute("src", "https://api.test/upright");
  expect(container.querySelector("svg")).toHaveAttribute("viewBox", "0 0 400 800");
});

test("corrected fields clear obsolete machine validation warnings", () => {
  render(<ReceiptForm detail={fixture()} busy={false} error="" onActive={vi.fn()} onSave={vi.fn()} onRead={vi.fn()} onDelete={vi.fn()} onDirty={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("Merchant", { exact: true }), { target: { value: "My shop" } });
  fireEvent.change(screen.getByLabelText("Total", { exact: true }), { target: { value: "135.00" } });
  expect(screen.getByText("Balanced.")).toBeVisible();
  expect(screen.queryByText(/Some amounts do not reconcile/)).not.toBeInTheDocument();
  expect(screen.queryByText(/Could not identify merchant/)).not.toBeInTheDocument();
});
