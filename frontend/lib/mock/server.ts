import { liveChecks } from "../checks";
import { receiptCsv, summarize } from "../journal";
import type { Box, Extraction, FieldValue, ReceiptDetail, ReceiptSummary, ReceiptUpdate } from "../types";
import { removeImage, storeImage } from "./images";
import samples from "./samples.json";

const STORE = "resiq.demo.receipts.v1";
const READ_TIME = 2800;
const SAMPLE_SIZE: Record<string, number> = { kapihan: 736, mercury: 664, petron: 628 };
type Sample = (typeof samples)[number];
type RecordEntry = { detail: ReceiptDetail; sample: string | null; started: number; hasUpload?: boolean };
const json = (body: unknown, status = 200) => Response.json(body, { status });
const failure = (detail: string, status: number) => json({ detail }, status);
const load = (): RecordEntry[] => JSON.parse(localStorage.getItem(STORE) ?? "[]");
const save = (entries: RecordEntry[]) => localStorage.setItem(STORE, JSON.stringify(entries));
const lineBox = (line: number): Box => [27, 40 + line * 36, 509, 72 + line * 36];
const empty = (): FieldValue<string> => ({ value: null, confidence: 0, source: null, box: null });

function sampleDetail(base: ReceiptDetail, sample: Sample): ReceiptDetail {
  const ocr_lines = sample.lines.flatMap((line, index) => {
    const text = line.c ?? [line.t, line.r].filter(Boolean).join("  ");
    return text ? [{ text, confidence: 0.93, box: lineBox(index) }] : [];
  });
  function field(key: keyof Sample["fields"]): FieldValue<string> {
    const { line, value, conf } = sample.fields[key];
    const box = lineBox(line);
    const amount = ["total", "vat_amount", "vatable_sales"].includes(key);
    if (amount) box[0] = 347;
    return { value, confidence: conf, source: amount ? sample.lines[line].r ?? null : ocr_lines.find((row) => row.box[1] === box[1])?.text ?? null, box };
  }
  const extraction: Extraction = {
    merchant: field("merchant"), merchant_tin: field("merchant_tin"), receipt_number: field("receipt_number"),
    receipt_date: field("receipt_date"), vatable_sales: field("vatable_sales"), vat_amount: field("vat_amount"),
    subtotal: empty(), vat_exempt: empty(), total: field("total"),
    line_items: sample.items.map(({ line, ...item }) => ({ ...item, box: lineBox(line), confidence: 0.91 })),
    category: { ...empty(), value: sample.category, confidence: 0.8 }, checks: [], warnings: [], engine_version: "resiq-sample-v1",
  };
  const warnings = sample.blurry ? ["This photo is a little blurry. Check the figures against the receipt."] : [];
  const detail: ReceiptDetail = {
    ...base, status: "needs_review", merchant: extraction.merchant.value, merchant_tin: extraction.merchant_tin.value,
    receipt_number: extraction.receipt_number.value, receipt_date: extraction.receipt_date.value,
    vatable_sales: extraction.vatable_sales.value, vat_amount: extraction.vat_amount.value, total: extraction.total.value,
    category: sample.category, line_items: sample.items.map(({ description, quantity, unit_price, amount }, position) => ({ description, quantity, unit_price, amount, position })),
    extraction, ocr_lines, quality: { blur_score: sample.blurry ? 35 : 150, is_blurry: Boolean(sample.blurry), brightness: 180, is_dark: false, skew_angle: 0, document_found: true, warnings },
  };
  extraction.checks = liveChecks(detail);
  return detail;
}

function settle(entries: RecordEntry[]) {
  let changed = false;
  for (const entry of entries) {
    if (entry.detail.status !== "queued" && entry.detail.status !== "processing") continue;
    const elapsed = Date.now() - entry.started;
    if (elapsed >= READ_TIME) {
      const sample = samples.find((sample) => sample.key === entry.sample);
      entry.detail = sample ? sampleDetail(entry.detail, sample) : { ...entry.detail, status: "failed", error: "Automatic reading is available for the sample receipts in this demo. You can enter this receipt by hand." };
      changed = true;
    } else if (elapsed > 300 && entry.detail.status === "queued") {
      entry.detail.status = "processing";
      changed = true;
    }
  }
  if (changed) save(entries);
}

async function findSample(file: File) {
  const candidate = samples.find((sample) => file.name === sample.key + ".png");
  if (!candidate) return null;
  try {
    const response = await fetch("/samples/" + candidate.key + ".png");
    if (!response.ok) return null;
    const [actual, expected] = await Promise.all([file.arrayBuffer(), response.arrayBuffer()]);
    const bytes = new Uint8Array(expected);
    return actual.byteLength === bytes.length && new Uint8Array(actual).every((byte, i) => byte === bytes[i]) ? candidate : null;
  } catch {
    return null;
  }
}

async function create(file: File, sample: Sample | null) {
  const id = crypto.randomUUID();
  const src = sample ? "/samples/" + sample.key + ".png" : await storeImage(id, file);
  const detail: ReceiptDetail = {
    id, status: "queued", merchant: null, receipt_number: null, receipt_date: null, total: null, category: null,
    thumbnail_url: src, created_at: new Date().toISOString(), error: null, merchant_tin: null, subtotal: null,
    vatable_sales: null, vat_amount: null, vat_exempt: null, line_items: [], extraction: null, quality: null, ocr_lines: [],
    image: { original_url: src, processed_url: src, width: sample ? 536 : 0, height: sample ? SAMPLE_SIZE[sample.key] : 0 },
    stages: sample ? { original: src, warped: src, enhanced: src } : { original: src }, verified_at: null,
  };
  try {
    save([{ detail, sample: sample?.key ?? null, started: Date.now(), hasUpload: !sample }, ...load()]);
  } catch (error) {
    if (!sample) await removeImage(id);
    throw error;
  }
  return json({ id, status: detail.status }, 202);
}

const summary = (row: ReceiptDetail): ReceiptSummary => ({
  id: row.id, status: row.status, merchant: row.merchant, receipt_number: row.receipt_number, receipt_date: row.receipt_date,
  total: row.total, category: row.category, thumbnail_url: row.thumbnail_url, created_at: row.created_at, error: row.error,
});

export async function mockFetch(path: string, init: RequestInit): Promise<Response> {
  const url = new URL(path, "https://resiq.local");
  const method = init.method ?? "GET";
  const { pathname, searchParams: query } = url;
  if (pathname === "/api/receipts" && method === "POST") {
    const file = (init.body as FormData).get("file");
    if (!file || typeof file === "string") return failure("Choose a receipt photo first.", 400);
    if (file.size > 10 * 1024 * 1024) return failure("This photo is too large: use one under 10 MB.", 413);
    return create(file, await findSample(file));
  }
  const entries = load();
  settle(entries);
  const rows = entries.map((entry) => entry.detail);
  const month = query.get("month");
  const inMonth = (row: ReceiptDetail) => !month || (row.receipt_date ?? row.created_at).startsWith(month);
  if (pathname === "/api/journal/months") return json([...new Set(rows.filter((row) => row.status === "verified").flatMap((row) => row.receipt_date ? [row.receipt_date.slice(0, 7)] : []))].sort().reverse());
  if (pathname === "/api/journal") {
    const list = rows.filter((row) => inMonth(row) && row.status === "verified");
    const offset = Math.max(0, list.findIndex((row) => row.id === query.get("cursor")) + 1);
    const items = list.slice(offset, offset + 50);
    return json({ items, next_cursor: offset + 50 < list.length ? items.at(-1)?.id : null });
  }
  if (pathname === "/api/receipts" && method === "GET") {
    const status = query.get("status");
    const q = query.get("q")?.trim().toLowerCase();
    const list = rows.filter((row) => inMonth(row) && (!status || row.status === status) && (!q || [row.merchant, row.receipt_number].some((value) => value?.toLowerCase().includes(q))));
    const offset = Math.max(0, list.findIndex((row) => row.id === query.get("cursor")) + 1);
    const limit = Math.max(1, Math.min(100, Number(query.get("limit")) || 50));
    const items = list.slice(offset, offset + limit).map(summary);
    return json({ items, next_cursor: offset + limit < list.length ? items.at(-1)?.id : null });
  }
  if (method === "GET" && ["/api/receipts/export.csv", "/api/stats/summary"].includes(pathname)) {
    const journal = rows.filter((row) => inMonth(row) && row.status === "verified");
    return pathname.endsWith(".csv")
      ? new Response(receiptCsv(journal), { headers: { "content-type": "text/csv; charset=utf-8" } })
      : json(summarize(month ?? "", journal));
  }
  const match = /^\/api\/receipts\/([^/]+)(\/reprocess)?$/.exec(pathname);
  const entry = entries.find((record) => record.detail.id === match?.[1]);
  if (!entry) return failure("This receipt could not be found.", 404);
  const { detail } = entry;
  if (match?.[2] && method === "POST") {
    if (detail.status === "verified" && query.get("force") !== "true") return failure("Confirm before reading a saved receipt again.", 409);
    entry.detail = { ...detail, status: "queued", error: null, verified_at: null };
    entry.started = Date.now();
    save(entries);
    return json({ id: detail.id, status: "queued" }, 202);
  }
  if (!match?.[2] && method === "GET") return json(detail);
  if (!match?.[2] && method === "PUT") {
    if (detail.status === "queued" || detail.status === "processing") return failure("This receipt is still being read.", 409);
    const update = JSON.parse(String(init.body)) as ReceiptUpdate;
    entry.detail = { ...detail, ...update, status: "verified", verified_at: new Date().toISOString(), error: null };
    save(entries);
    return json(entry.detail);
  }
  if (!match?.[2] && method === "DELETE") {
    if (entry.hasUpload) await removeImage(detail.id);
    save(load().filter((record) => record.detail.id !== detail.id));
    return new Response(null, { status: 204 });
  }
  return failure("This action is not available.", 405);
}
