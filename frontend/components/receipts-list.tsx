"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { keepPreviousData, useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { formatDate, formatMonth, isMonth, monthOptions, SAMPLE_MONTH } from "@/lib/format";
import { formatPeso } from "@/lib/money";
import { errorText, isReading, listReceipts, readAgain } from "@/lib/receipts";
import type { ReceiptStatus } from "@/lib/types";
import { ReceiptImage } from "./receipt-image";
import { Button, ButtonLink, ErrorNotice, Skeleton, StatusChip, TopBar } from "./resiq/ui";

const statuses = [["", "All"], ["needs_review", "Needs review"], ["verified", "Verified"], ["failed", "Could not read"]] as const;
type FilterField = "status" | "month" | "q";

export function ReceiptsList() {
  const search = useSearchParams();
  const rawStatus = search.get("status") ?? "";
  const rawMonth = search.get("month") ?? "";
  const status = (statuses.some(([value]) => value === rawStatus) ? rawStatus : "") as ReceiptStatus | "";
  const month = isMonth(rawMonth) ? rawMonth : "";
  const q = search.get("q")?.trim() ?? "";
  const filters = { status, month, q };
  const client = useQueryClient();
  const searchInput = useRef<HTMLInputElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [retryError, setRetryError] = useState("");
  useEffect(() => {
    function onPopState() {
      if (timer.current) clearTimeout(timer.current);
      if (searchInput.current) searchInput.current.value = new URLSearchParams(location.search).get("q") ?? "";
    }
    window.addEventListener("popstate", onPopState);
    return () => { if (timer.current) clearTimeout(timer.current); window.removeEventListener("popstate", onPopState); };
  }, []);

  function filter(field: FilterField, value: string, replace = false) {
    const next = new URLSearchParams(window.location.search);
    if (value) next.set(field, value); else next.delete(field);
    const url = "/receipts" + (next.size ? "?" + next : "");
    if (replace) window.history.replaceState(null, "", url); else window.history.pushState(null, "", url);
  }

  const query = useInfiniteQuery({
    queryKey: ["receipts", filters], queryFn: ({ pageParam }) => listReceipts(filters, pageParam ?? undefined),
    initialPageParam: null as string | null, getNextPageParam: (page) => page.next_cursor,
    placeholderData: keepPreviousData,
    refetchInterval: (query) => query.state.data?.pages.some((page) => page.items.some((row) => isReading(row.status))) ? 1500 : false,
  });
  const retry = useMutation({
    mutationFn: (id: string) => readAgain(id),
    onMutate: () => setRetryError(""),
    onError: (error) => setRetryError(errorText(error)),
    onSuccess: (_, id) => {
      void client.invalidateQueries({ queryKey: ["receipts"] });
      void client.invalidateQueries({ queryKey: ["receipt", id] });
    },
  });
  const rows = query.data?.pages.flatMap((page) => page.items) ?? [];
  const needsReview = rows.filter((row) => row.status === "needs_review").length;
  const isFiltered = Boolean(status || month || q);
  const months = monthOptions([month, SAMPLE_MONTH, ...rows.map((row) => (row.receipt_date ?? row.created_at).slice(0, 7))]);

  return <><TopBar current="receipts" /><main id="main" className="app-container screen">
    <div className="screen-heading"><div><h1>Receipts</h1>
      {query.data && <p>{query.hasNextPage ? "Showing " : ""}{rows.length} {rows.length === 1 ? "receipt" : "receipts"}{needsReview ? ", " + needsReview + (needsReview === 1 ? " needs review" : " need review") : ""}.</p>}
    </div></div>
    <div className="filters">
      <fieldset className="filter-status"><legend className="visually-hidden">Receipt status</legend>
        <div className="status-options">{statuses.map(([value, label]) => <label key={label} className="status-option">
          <input className="visually-hidden" type="radio" name="receipt-status" value={value} checked={status === value}
            onChange={() => filter("status", value)} /><span>{label}</span></label>)}</div>
      </fieldset>
      <div className="filter-fields">
        <div className="field"><label htmlFor="receipt-month">Month</label><select id="receipt-month" value={month} onChange={(event) => filter("month", event.target.value)}>
          <option value="">All months</option>{months.map((value) => <option key={value} value={value}>{formatMonth(value, true)}</option>)}
        </select></div>
        <div className="field"><label htmlFor="receipt-search">Search receipts</label><input id="receipt-search" type="search" defaultValue={q}
          placeholder="Merchant or OR no." ref={searchInput} onChange={(event) => {
            if (timer.current) clearTimeout(timer.current);
            const value = event.target.value.trim();
            timer.current = setTimeout(() => filter("q", value, true), 300);
          }} /></div>
      </div>
    </div>
    {retryError && <ErrorNotice>{retryError}</ErrorNotice>}
    {query.isPending ? <Skeleton label="Loading receipts…" /> : query.isError && !query.data ? <ErrorNotice retry={() => void query.refetch()}>{errorText(query.error)}</ErrorNotice>
      : !rows.length ? <div className="empty-state"><h2>{isFiltered ? "No receipts match these filters." : "No receipts yet."}</h2>
        {isFiltered ? <Button onClick={() => {
          if (timer.current) clearTimeout(timer.current);
          if (searchInput.current) searchInput.current.value = "";
          window.history.pushState(null, "", "/receipts");
        }}>Clear filters</Button> : <ButtonLink href="/upload" variant="primary">Upload a receipt</ButtonLink>}
      </div> : <div className="receipts-results" aria-busy={query.isPlaceholderData}>
        <table className="receipt-table">
          <caption className="visually-hidden">Receipts in this workspace</caption>
          <thead><tr><th scope="col">Particulars</th><th scope="col">Date</th><th scope="col">Category</th><th scope="col">Amount</th><th scope="col">Status</th></tr></thead>
          <tbody>{rows.map((row) => <tr key={row.id}>
            <td><div className="receipt-particulars">
              {row.thumbnail_url ? <ReceiptImage className="thumbnail" src={row.thumbnail_url} alt="" /> : <span className="thumbnail thumbnail--blank" aria-hidden="true" />}
              <div><Link className="link" href={"/receipts/" + row.id}>{row.merchant || (isReading(row.status) ? "Reading receipt" : "Untitled receipt")}</Link>
                {row.receipt_number && <small className="meta">OR no. {row.receipt_number}</small>}</div>
            </div></td>
            <td>{formatDate(row.receipt_date)}</td><td>{row.category || "—"}</td><td className="num">{formatPeso(row.total)}</td>
            <td><div className="row-status"><StatusChip status={row.status} />
              {row.status === "failed" && <><Button disabled={retry.isPending} onClick={() => retry.mutate(row.id)}>Try again</Button>
                {row.error && <small className="meta row-error">{row.error}</small>}</>}
            </div></td>
          </tr>)}</tbody>
        </table>
        {query.isFetchNextPageError && <ErrorNotice>{errorText(query.error)}</ErrorNotice>}
        {query.hasNextPage && <Button className="more-receipts" onClick={() => void query.fetchNextPage()} disabled={query.isFetchingNextPage}>{query.isFetchingNextPage ? "Loading…" : "Load more receipts"}</Button>}
      </div>}
  </main></>;
}
