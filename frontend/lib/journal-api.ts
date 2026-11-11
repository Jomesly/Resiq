import { apiFetch, apiRaw } from "./api";
import type { JournalList, MonthlySummary } from "./types";

export const listJournal = (month: string, cursor?: string) => {
  const query = new URLSearchParams({ month });
  if (cursor) query.set("cursor", cursor);
  return apiFetch<JournalList>("/api/journal?" + query);
};
export const journalMonths = () => apiFetch<string[]>("/api/journal/months");
export const journalSummary = (month: string) => apiFetch<MonthlySummary>("/api/stats/summary?" + new URLSearchParams({ month }));
export const journalCsv = async (month: string) => (await apiRaw("/api/receipts/export.csv?" + new URLSearchParams({ month }))).text();
