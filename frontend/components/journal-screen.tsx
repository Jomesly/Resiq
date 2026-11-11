"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { currentMonth, formatMonth, isMonth, monthOptions } from "@/lib/format";
import { saveCsv } from "@/lib/journal";
import { journalCsv, journalMonths, journalSummary, listJournal } from "@/lib/journal-api";
import { formatPeso } from "@/lib/money";
import { errorText } from "@/lib/receipts";
import { JournalTable } from "./journal-table";
import { SpendChart } from "./spend-chart";
import { Button, ButtonLink, ErrorNotice, Skeleton, TopBar } from "./resiq/ui";

export function JournalScreen() {
  const search = useSearchParams();
  const value = search.get("month") ?? "";
  const month = isMonth(value) ? value : currentMonth();
  const label = formatMonth(month);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const query = useInfiniteQuery({
    queryKey: ["journal", month, "entries"], initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => listJournal(month, pageParam),
    getNextPageParam: (page) => page.next_cursor ?? undefined,
  });
  const totals = useQuery({ queryKey: ["journal", month, "summary"], queryFn: () => journalSummary(month) });
  const monthIndex = useQuery({
    queryKey: ["journal", "month-index"], queryFn: journalMonths,
  });
  const rows = query.data?.pages.flatMap((page) => page.items) ?? [];
  const summary = totals.data;
  const months = monthOptions([month, ...(monthIndex.data ?? [])]);

  async function exportCsv() {
    setExporting(true); setExportError("");
    try { saveCsv("resiq-" + month + ".csv", await journalCsv(month)); }
    catch (error) { setExportError(errorText(error)); }
    finally { setExporting(false); }
  }

  return <><TopBar current="journal" /><main id="main" className="app-container screen journal-screen">
    <div className="screen-heading"><div><h1>{formatMonth(month, true)}</h1><p>Your receipt journal.</p></div>
      <div className="field"><label htmlFor="journal-month">Journal month</label>
        <select id="journal-month" value={month} onChange={(event) => window.history.pushState(null, "", "/journal?month=" + event.target.value)}>
          {months.map((value) => <option key={value} value={value}>{formatMonth(value, true)}</option>)}
        </select>
      </div>
    </div>
    {monthIndex.isError && <ErrorNotice retry={() => void monthIndex.refetch()}>Could not load the list of journal months.</ErrorNotice>}
    {query.isPending || totals.isPending ? <Skeleton label="Opening journal…" /> : query.isError || totals.isError ? <ErrorNotice retry={() => { void query.refetch(); void totals.refetch(); }}>{errorText(query.error ?? totals.error)}</ErrorNotice>
      : !rows.length ? <div className="empty-state"><h2>Nothing in {label} yet.</h2><p>Save a reviewed receipt to put it in your journal.</p>
        <div className="button-group"><ButtonLink href="/upload" variant="primary">Upload a receipt</ButtonLink><ButtonLink href="/receipts">View receipts</ButtonLink></div>
      </div> : <>
        {summary && <><dl className="journal-summary">
          <div><dt>Total spent</dt><dd>{formatPeso(summary.total)}</dd></div>
          <div><dt>Receipts</dt><dd>{summary.count}</dd></div>
          <div><dt>VAT paid</dt><dd>{formatPeso(summary.vat_total)}</dd></div>
        </dl>
        <SpendChart categories={summary.by_category} /></>}
        <section className="journal-entries" aria-labelledby="entries-title"><div className="section-toolbar"><h2 id="entries-title">Journal entries</h2>
          <Button variant="primary" disabled={exporting} onClick={() => void exportCsv()}>{exporting ? "Preparing CSV…" : `Export ${label} as CSV`}</Button>
        </div>
          {exportError && <ErrorNotice retry={() => void exportCsv()}>{exportError}</ErrorNotice>}
          <JournalTable rows={rows} label={label + " journal entries"} partial={query.hasNextPage} />
          {query.hasNextPage && <Button disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>{query.isFetchingNextPage ? "Loading…" : "Load more entries"}</Button>}
        </section>
      </>}
  </main></>;
}
