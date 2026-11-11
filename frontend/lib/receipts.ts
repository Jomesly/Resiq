import { API_BASE, ApiError, apiFetch } from "./api";
import { getToken } from "./workspace";
import type { ListFilters, ReceiptDetail, ReceiptList, ReceiptStatus, ReceiptUpdate } from "./types";

type UploadResult = { id: string; status: ReceiptStatus };
const basePath = "/api/receipts";
const receiptPath = (id: string) => basePath + "/" + encodeURIComponent(id);

export async function uploadReceipt(file: File, onProgress: (pct: number) => void): Promise<UploadResult> {
  const body = new FormData();
  body.set("file", file);
  if (!API_BASE) {
    const result = await apiFetch<UploadResult>(basePath, { method: "POST", body });
    onProgress(100);
    return result;
  }

  const send = (token: string) => new Promise<UploadResult>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", API_BASE + basePath);
    xhr.timeout = 90_000;
    xhr.setRequestHeader("Authorization", "Bearer " + token);
    xhr.responseType = "json";
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.min(99, Math.round(100 * event.loaded / event.total)));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300 && xhr.response?.id) {
        onProgress(100);
        resolve(xhr.response as UploadResult);
      } else {
        reject(new ApiError(xhr.status, typeof xhr.response?.detail === "string" ? xhr.response.detail : "Could not upload this photo."));
      }
    };
    xhr.onerror = xhr.ontimeout = () => reject(new Error("The upload did not finish. Check your connection and try again."));
    xhr.send(body);
  });

  try {
    return await send(await getToken(API_BASE));
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401) throw error;
    throw new ApiError(401, "This workspace could not be opened. Your token has been kept. Check the server connection and retry.");
  }
}

export function listReceipts(filters: ListFilters = {}, cursor?: string) {
  const query = new URLSearchParams();
  if (filters.status) query.set("status", filters.status);
  if (filters.month) query.set("month", filters.month);
  if (filters.q) query.set("q", filters.q);
  if (cursor) query.set("cursor", cursor);
  return apiFetch<ReceiptList>(basePath + "?" + query);
}

export async function listAllReceipts(filters: ListFilters = {}) {
  const rows = [];
  const seen = new Set<string>();
  let cursor: string | null = null;
  do {
    const page: ReceiptList = await listReceipts(filters, cursor ?? undefined);
    rows.push(...page.items);
    cursor = page.next_cursor;
    if (cursor) {
      if (seen.has(cursor)) throw new Error("Could not finish loading receipts.");
      seen.add(cursor);
    }
  } while (cursor);
  return rows;
}

export const getReceipt = (id: string) => apiFetch<ReceiptDetail>(receiptPath(id));
export const deleteReceipt = (id: string) => apiFetch<void>(receiptPath(id), { method: "DELETE" });
export const readAgain = (id: string, force = false) => apiFetch<UploadResult>(receiptPath(id) + "/reprocess?force=" + force, { method: "POST" });
export const updateReceipt = (id: string, entry: ReceiptUpdate) => apiFetch<ReceiptDetail>(receiptPath(id), {
  method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify(entry),
});
export const isReading = (status?: ReceiptStatus) => status === "queued" || status === "processing";
export const errorText = (error: unknown) => error instanceof Error ? error.message : "Something went wrong. Please try again.";

export function receiptImageUrl(src: string) {
  return API_BASE && src.startsWith("/") && !src.startsWith("//") ? new URL(src, API_BASE).href : src;
}
