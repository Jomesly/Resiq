"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { isBalanced } from "@/lib/checks";
import { amountFields, entryInputId, fieldLabels, headFields } from "@/lib/entry";
import { currentMonth, formatMonth } from "@/lib/format";
import { formatPeso } from "@/lib/money";
import { deleteReceipt, errorText, getReceipt, isReading, listAllReceipts, readAgain, updateReceipt } from "@/lib/receipts";
import type { ReceiptDetail, ReceiptUpdate } from "@/lib/types";
import { ReceiptForm } from "./receipt-form";
import { ReceiptViewer, type FieldBox } from "./receipt-viewer";
import { Button, ButtonLink, Chip, ErrorNotice, Skeleton, StatusChip, TopBar } from "./resiq/ui";

function fieldBoxes(detail: ReceiptDetail): FieldBox[] {
  const extraction = detail.extraction;
  if (!extraction) return [];
  return [
    ...[...headFields, ...amountFields].flatMap((field) => {
      const box = extraction[field].box;
      return box ? [{ id: entryInputId(detail.id, field), label: fieldLabels[field], box }] : [];
    }),
    ...extraction.line_items.map(({ box, description }, index) => ({ id: "source-line-" + index, label: "line item " + description, box })),
  ];
}

function ReadingState({ detail }: { detail: ReceiptDetail }) {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const timer = window.setInterval(() => setStep(Math.min(2, Math.floor((Date.now() - started) / 1100))), 350);
    return () => clearInterval(timer);
  }, []);
  return <div className="state"><StatusChip status={detail.status} /><h1>Reading your receipt</h1>
    <ol className="steps" aria-label="Reading steps">
      {["Straighten", "Read the lines", "Fill the entry"].map((label, index) => <li key={label} className={index < step ? "done" : ""}
        aria-current={index === step ? "step" : undefined}>{label}</li>)}
    </ol><div className="skeleton-group" aria-hidden="true"><span className="skeleton" /><span className="skeleton" /></div>
  </div>;
}

export function ReceiptReview({ id }: { id: string }) {
  const router = useRouter();
  const client = useQueryClient();
  const [active, setActive] = useState<string | null>(null);
  const [manual, setManual] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<ReceiptDetail | null>(null);
  const [confirm, setConfirm] = useState<"delete" | "read">("delete");
  const [formVersion, setFormVersion] = useState(0);
  const main = useRef<HTMLElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const dirty = useRef(false);
  const discardOnHide = useRef(false);
  const onDirty = useCallback((value: boolean) => { dirty.current = value; }, []);
  const query = useQuery({ queryKey: ["receipt", id], queryFn: () => getReceipt(id),
    refetchInterval: (query) => isReading(query.state.data?.status) ? 950 : 60_000 });
  const detail = query.data;
  const reviewList = useQuery({ queryKey: ["receipts", "review-order"], queryFn: () => listAllReceipts({ status: "needs_review" }),
    enabled: detail?.status === "needs_review" || Boolean(saved) });
  const candidates = reviewList.data ?? [];
  const index = candidates.findIndex((row) => row.id === id);
  const next = index === -1 ? candidates.find((row) => row.id !== id) : candidates[index + 1] ?? candidates.find((row) => row.id !== id);
  const previous = index > 0 ? candidates[index - 1] : undefined;

  // Cache Components keep recent pages mounted. Clear transient confirmations when this page is hidden.
  useLayoutEffect(() => {
    const modal = dialog.current;
    return () => {
      setSaved(null);
      if (modal?.open) modal.close();
      if (discardOnHide.current) {
        discardOnHide.current = false;
        setFormVersion((version) => version + 1);
      }
    };
  }, []);

  useEffect(() => {
    const guard = (event: BeforeUnloadEvent) => {
      if (dirty.current) { event.preventDefault(); event.returnValue = ""; }
    };
    const guardLink = (event: MouseEvent) => {
      if (!dirty.current || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
      const target = (event.target as Element).closest("a[href]");
      if (!target || target.getAttribute("href")?.startsWith("#") || target.getAttribute("target") === "_blank") return;
      if (window.confirm("Leave this receipt? Your unsaved changes will be lost.")) discardOnHide.current = true;
      else { event.preventDefault(); event.stopPropagation(); }
    };
    const shortcuts = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey || dialog.current?.open ||
          (event.target instanceof HTMLElement && event.target.closest("input, select, textarea, button, [contenteditable]"))) return;
      const row = event.key.toLowerCase() === "j" ? next : event.key.toLowerCase() === "k" ? previous : undefined;
      if (!row || (dirty.current && !window.confirm("Leave this receipt? Your unsaved changes will be lost."))) return;
      discardOnHide.current = dirty.current;
      router.push("/receipts/" + row.id);
    };
    window.addEventListener("beforeunload", guard);
    document.addEventListener("click", guardLink, true);
    document.addEventListener("keydown", shortcuts);
    return () => {
      window.removeEventListener("beforeunload", guard);
      document.removeEventListener("click", guardLink, true);
      document.removeEventListener("keydown", shortcuts);
    };
  }, [next, previous, router]);

  function focusBox(id: string) {
    const field = id.startsWith("source-line-")
      ? main.current?.querySelector<HTMLElement>('[data-source-line="' + id + '"]')
      : document.getElementById(id);
    if (field) { field.focus({ preventScroll: true }); field.scrollIntoView({ block: "nearest" }); }
  }

  async function perform(work: () => Promise<void>) {
    setBusy(true); setError("");
    try { await work(); }
    catch (error) { setError(errorText(error)); }
    finally { setBusy(false); }
  }

  function refresh(receipt: ReceiptDetail) {
    client.setQueryData(["receipt", id], receipt);
    void client.invalidateQueries({ queryKey: ["receipts"] });
    void client.invalidateQueries({ queryKey: ["journal"] });
  }

  function save(entry: ReceiptUpdate) {
    void perform(async () => {
      const verified = await updateReceipt(id, entry);
      dirty.current = false;
      refresh(verified);
      setSaved(verified);
    });
  }

  function reprocess() {
    void perform(async () => {
      if (!detail) return;
      await readAgain(id, detail.status === "verified");
      dirty.current = false;
      setSaved(null);
      setManual(false);
      refresh({ ...detail, status: "queued", error: null });
      void query.refetch();
    });
  }

  function remove() {
    void perform(async () => {
      await deleteReceipt(id);
      dirty.current = false;
      void client.invalidateQueries({ queryKey: ["receipts"] });
      void client.invalidateQueries({ queryKey: ["journal"] });
      router.replace("/receipts");
    });
  }

  function confirmAction(action: typeof confirm) {
    setConfirm(action);
    dialog.current?.showModal();
  }

  const canEdit = detail && !isReading(detail.status) && (detail.status !== "failed" || manual) && !saved;
  const journalMonth = saved?.receipt_date?.slice(0, 7) || currentMonth();

  return <><TopBar current="receipts" /><main id="main" className="app-container" ref={main}>
    <nav className="crumbs" aria-label="Breadcrumb"><Link href="/receipts">Receipts</Link><span aria-hidden="true">/</span><span aria-current="page">{detail?.merchant ?? "Receipt"}</span></nav>
    {query.isPending ? <div className="review-loading"><Skeleton label="Opening receipt…" /></div>
      : !detail ? <div className="review-loading"><ErrorNotice retry={() => void query.refetch()}>{errorText(query.error)}</ErrorNotice></div>
      : <div className="review">
        <ReceiptViewer key={isReading(detail.status) ? "reading" : "preview"} detail={detail} activeId={active} boxes={canEdit ? fieldBoxes(detail) : []} onBoxClick={focusBox} />
        {saved ? <div className="state" role="status">
          <Chip tone="ok">{isBalanced(saved) ? "Balanced" : "Verified"}</Chip>
          <h1>Saved to {formatMonth(journalMonth)}</h1><p>{formatPeso(saved.total)} is now in your journal.</p>
          <div className="button-group">
            <ButtonLink variant="primary" href={"/journal?month=" + journalMonth}>Open journal</ButtonLink>
            {next && <ButtonLink href={"/receipts/" + next.id}>Next receipt</ButtonLink>}
            <Button onClick={() => setSaved(null)}>Back to receipt</Button>
          </div>
        </div> : isReading(detail.status) ? <ReadingState detail={detail} />
          : detail.status === "failed" && !manual ? <div className="state">
            <StatusChip status="failed" /><h1>Could not read this receipt</h1><p>{detail.error || "No text found in this photo."}</p>
            {error && <ErrorNotice>{error}</ErrorNotice>}
            <div className="button-group">
              <Button variant="primary" onClick={() => setManual(true)} disabled={busy}>Enter it by hand</Button>
              <Button onClick={reprocess} disabled={busy}>Read again</Button>
              <Button variant="quiet" onClick={() => confirmAction("delete")} disabled={busy}>Delete</Button>
            </div>
          </div> : <ReceiptForm key={(detail.verified_at ?? detail.status) + ":" + formVersion} detail={detail} busy={busy} error={error} onActive={setActive}
            onSave={save} onDirty={onDirty} onDelete={() => confirmAction("delete")}
            onRead={() => detail.status === "verified" || dirty.current ? confirmAction("read") : reprocess()} />}
      </div>}
    <dialog className="confirm-dialog" ref={dialog} aria-labelledby={"confirm-" + id}>
      <form method="dialog"><h2 id={"confirm-" + id}>{confirm === "delete" ? "Delete this receipt?" : "Read this receipt again?"}</h2>
        <p>{confirm === "delete" ? "The photo and its entry will be removed." : "Reading again replaces the current entry with a new reading."}</p>
        <div className="button-group">
          <Button type="submit" autoFocus>Cancel</Button>
          <Button variant={confirm === "delete" ? "quiet" : "primary"} onClick={() => {
            dialog.current?.close(); if (confirm === "delete") remove(); else reprocess();
          }}>{confirm === "delete" ? "Delete receipt" : "Read again"}</Button>
        </div>
      </form>
    </dialog>
  </main></>;
}
