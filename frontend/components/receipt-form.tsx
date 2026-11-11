"use client";

import { useEffect, useRef, useState, type FocusEvent, type FormEvent } from "react";
import { useFieldArray, useForm, useWatch } from "react-hook-form";
import { isBalanced, liveChecks } from "@/lib/checks";
import { amountFields, entryFromReceipt, entryInputId, fieldLabels, headFields, validateEntry, type EntryField } from "@/lib/entry";
import { formatDateTime } from "@/lib/format";
import { centsToString, normalizeMoney, toCents } from "@/lib/money";
import { CATEGORIES, type LineItem, type ReceiptDetail, type ReceiptUpdate } from "@/lib/types";
import { Button, Chip, ClosingRule, StatusChip } from "./resiq/ui";

const emptyLine: LineItem = { description: "", quantity: null, unit_price: null, amount: null, position: 0 };
const itemColumns = [["description", "Particulars"], ["quantity", "Qty"], ["unit_price", "Unit price"], ["amount", "Amount"]] as const;
type ItemKey = (typeof itemColumns)[number][0];
type Issues = { id: string; label: string; message: string }[];
const fieldIsMoney = (field: EntryField) => (amountFields as readonly string[]).includes(field);
const nullable = (value: string) => value === "" ? null : value;

function CheckBanner({ entry, detail }: { entry: ReceiptUpdate; detail: ReceiptDetail }) {
  const checks = liveChecks(entry);
  const balanced = isBalanced(entry, checks);
  const failed = checks.filter((check) => !check.passed);
  // Machine diagnostics describe the original reading. Current arithmetic comes
  // from liveChecks, and required fields must reflect the user's corrections.
  const warnings = (detail.extraction?.warnings ?? []).filter((warning) => !/line items.*(add|sum)|does not balance|amounts do not reconcile|could not identify/i.test(warning));
  for (const field of ["merchant", "receipt_date", "total"] as const) {
    if (!entry[field]?.trim()) warnings.push(`Enter ${fieldLabels[field].toLowerCase()} before saving.`);
  }
  return <div role="status" className={"balance-banner " + (balanced ? "is-ok" : failed.length ? "is-error" : "is-neutral")}>
    {balanced ? <p><strong>Balanced.</strong> {checks.filter((check) => check.name !== "items_sum").map((check) => check.detail).join(" ") || checks[0]?.detail}</p>
      : failed.length ? failed.map((check) => <p key={check.name}>{check.name === "subtotal_vat_total" ? <>
        <strong>{check.detail.split(". ")[0]}.</strong>{" "}{check.detail.split(". ").slice(1).join(". ")}
      </> : check.detail}</p>)
      : <p><strong>Balance not checked.</strong> Add VAT figures or line items to check the total.</p>}
    {warnings.map((warning) => <p key={warning}>{warning}</p>)}
  </div>;
}

function Field({ id, field, value, original, edited, issue, onChange, onActive }: {
  id: string; field: EntryField; value: string | null; original: ReceiptDetail["extraction"];
  edited: boolean; issue?: string; onChange: (value: string | null) => void; onActive: (id: string | null) => void;
}) {
  const reading = original?.[field];
  const money = fieldIsMoney(field);
  const suggested = field === "category" && reading?.value && !edited;
  const check = field !== "category" && reading?.value != null && reading.confidence < .7 && !edited;
  const source = check ? reading?.source : null;
  const aria = {
    "aria-invalid": issue ? true : undefined,
    "aria-describedby": [source ? id + "-source" : "", issue ? id + "-error" : ""].filter(Boolean).join(" ") || undefined,
    "aria-required": ["merchant", "receipt_date", "total"].includes(field) || undefined,
  };
  const numeric = money || field === "merchant_tin" || field === "receipt_number";
  const inputClass = (numeric ? "fig" : "") + (edited ? " is-edited" : "");
  return <div className={"field " + (money ? "amount-row" + (field === "total" ? " amount-row--total" : "") : field === "merchant" || field === "category" ? "field--wide" : "")}
    onPointerEnter={() => onActive(id)} onPointerLeave={(event) => { if (!event.currentTarget.contains(document.activeElement)) onActive(null); }}>
    <label htmlFor={id}>{fieldLabels[field]} {check && <Chip tone="check">Check</Chip>}{suggested && <Chip tone="busy">Suggested</Chip>}</label>
    {field === "category" ? <select id={id} value={value ?? ""} className={inputClass} {...aria}
      onFocus={() => onActive(id)} onBlur={() => onActive(null)} onChange={(event) => onChange(nullable(event.target.value))}>
      <option value="">Choose a category</option>
      {CATEGORIES.map((category) => <option key={category}>{category}</option>)}
    </select> : <input id={id} data-entry-field={field} value={value ?? ""} className={inputClass} {...aria} type={field === "receipt_date" ? "date" : "text"}
      inputMode={money ? "decimal" : undefined} onFocus={() => onActive(id)} onChange={(event) => onChange(nullable(event.target.value))}
      onBlur={(event) => {
        onActive(null);
        const value = event.currentTarget.value;
        if (money && value && normalizeMoney(value) !== value) onChange(normalizeMoney(value));
      }} />}
    {source && <small className="read" id={id + "-source"}>Read as {source}</small>}
    {issue && <small className="error read" id={id + "-error"}>{issue}</small>}
  </div>;
}

export function ReceiptForm({ detail, busy, error, onActive, onSave, onRead, onDelete, onDirty }: {
  detail: ReceiptDetail; busy: boolean; error: string; onActive: (id: string | null) => void;
  onSave: (entry: ReceiptUpdate) => void; onRead: () => void; onDelete: () => void; onDirty: (dirty: boolean) => void;
}) {
  const [initial] = useState(() => entryFromReceipt(detail));
  const { control, setValue, getValues, formState } = useForm<ReceiptUpdate>({ defaultValues: initial });
  const entry = useWatch({ control, defaultValue: initial }) as ReceiptUpdate;
  const { fields, append, remove } = useFieldArray({ control, name: "line_items" });
  const [touched, setTouched] = useState<Set<string>>(() => new Set());
  const [issues, setIssues] = useState<Issues>([]);
  const errorSummary = useRef<HTMLDivElement>(null);
  const form = useRef<HTMLFormElement>(null);
  const balanced = isBalanced(entry);
  const inputId = (field: string) => entryInputId(detail.id, field);
  const itemId = (index: number, field: string) => inputId("item-" + index + "-" + field);

  useEffect(() => { onDirty(formState.isDirty); return () => onDirty(false); }, [formState.isDirty, onDirty]);

  function mark(id: string, key = id) {
    setTouched((old) => old.has(key) ? old : new Set(old).add(key));
    setIssues((old) => old.filter((issue) => issue.id !== id));
  }

  function change(field: EntryField, value: string | null) {
    setValue(field, value, { shouldDirty: true });
    mark(inputId(field));
  }

  function edited(field: EntryField) {
    const candidate = detail.extraction?.[field].value ?? null;
    return touched.has(inputId(field)) || (detail.status === "verified" && (fieldIsMoney(field) ? toCents(candidate) !== toCents(initial[field]) : candidate !== initial[field]));
  }

  function changeItem(index: number, field: ItemKey, value: string) {
    const normalized = field === "description" ? value : nullable(value);
    setValue(`line_items.${index}.${field}`, normalized, { shouldDirty: true });
    mark(itemId(index, field), fields[index]?.id + "-" + field);
  }

  function finishItem(index: number, field: ItemKey, event: FocusEvent<HTMLInputElement>) {
    if (field === "amount" || field === "unit_price") {
      const value = event.currentTarget.value;
      if (normalizeMoney(value) !== value) changeItem(index, field, normalizeMoney(value));
    }
    if (field === "quantity" || field === "unit_price") {
      const item = getValues(`line_items.${index}`);
      const unit = toCents(item.unit_price);
      const quantity = item.quantity;
      if (!item.amount && quantity && /^\d+(\.\d{1,4})?$/.test(quantity) && unit !== null) {
        const [whole, fraction = ""] = quantity.split(".");
        const scale = 10 ** fraction.length;
        const product = Number(whole + fraction) * unit;
        if (Number.isSafeInteger(product)) changeItem(index, "amount", centsToString(Math.round(product / scale)));
      }
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const result = validateEntry(getValues());
    if (result.success) { setIssues([]); onSave(result.data); return; }
    const byField = new Map(result.error.issues.map(({ path, message }) => {
      if (path[0] === "line_items") {
        const index = Number(path[1]);
        const field = String(path[2]);
        const id = itemId(index, field);
        return [id, { id, label: "Line " + (index + 1) + ", " + (itemColumns.find(([key]) => key === field)?.[1] ?? field), message }] as const;
      }
      const field = path[0] as EntryField;
      const id = inputId(field);
      return [id, { id, label: fieldLabels[field], message }] as const;
    }));
    setIssues([...byField.values()]);
    requestAnimationFrame(() => errorSummary.current?.focus());
  }

  const renderField = (field: EntryField) => <Field key={field} id={inputId(field)} field={field} value={entry[field]} original={detail.extraction} edited={edited(field)}
    issue={issues.find((issue) => issue.id === inputId(field))?.message} onChange={(value) => change(field, value)} onActive={onActive} />;

  return <form className="entry-panel" ref={form} onSubmit={submit} noValidate onKeyDown={(event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") { event.preventDefault(); form.current?.requestSubmit(); }
  }}>
    <div className="entry-panel__head">
      {detail.status === "verified" ? <StatusChip status="verified" /> : balanced ? <Chip tone="ok">Ready to save</Chip> : <StatusChip status="needs_review" />}
      <h1>{entry.merchant?.trim() || "Untitled receipt"}</h1>
      <p className="meta">Uploaded {formatDateTime(detail.created_at)}</p>
    </div>
    {issues.length > 0 && <div className="notice notice--error form-error" ref={errorSummary} tabIndex={-1} role="alert">
      <strong>Check these fields before saving.</strong>
      <ul>{issues.map(({ id, label, message }, index) => <li key={id + index}><a href={"#" + id} onClick={(event) => {
        event.preventDefault(); document.getElementById(id)?.focus();
      }}>{label}: {message}</a></li>)}</ul>
    </div>}
    <CheckBanner entry={entry} detail={detail} />
    <fieldset className="entry-fields"><legend>Who and when</legend>{headFields.map(renderField)}</fieldset>
    <fieldset className={"entry-fields amounts" + (balanced ? " is-balanced" : "")}><legend>Amounts</legend>
      {amountFields.map(renderField)}
      <div className="closing-row">{balanced && <ClosingRule />}</div>
    </fieldset>
    <fieldset className="entry-fields items"><legend>Line items</legend>
      {fields.length > 0 ? <div className="items-scroll" role="region" aria-label="Line item fields" tabIndex={0}><table>
        <caption className="visually-hidden">Editable line items</caption>
        <thead><tr>{itemColumns.map(([key, label]) => <th key={key} scope="col" className={key === "description" ? "" : "number-head"}>{label}</th>)}<th scope="col"><span className="visually-hidden">Remove line</span></th></tr></thead>
        <tbody>{fields.map((row, index) => {
          const original = detail.extraction?.line_items ?? [];
          const initialRow = initial.line_items[row.position];
          const matches = initialRow ? original.flatMap((item, source) => item.description === initialRow.description && item.amount === initialRow.amount ? [source] : []) : [];
          const sourceIndex = detail.status !== "verified" || matches.includes(row.position) ? row.position
            : matches.length === 1 ? matches[0] : original.length === initial.line_items.length ? row.position : -1;
          const sourceId = original[sourceIndex] ? "source-line-" + sourceIndex : null;
          return <tr key={row.id} onPointerEnter={() => onActive(sourceId)}
          onPointerLeave={(event) => { if (!event.currentTarget.contains(document.activeElement)) onActive(null); }}>
          {itemColumns.map(([key, label]) => {
            const id = itemId(index, key);
            const issue = issues.find((issue) => issue.id === id)?.message;
            const originalItem = original[sourceIndex];
            const value = entry.line_items[index]?.[key] ?? "";
            const changed = touched.has(row.id + "-" + key) || (detail.status === "verified" && value !== (originalItem?.[key] ?? ""));
            return <td key={key}><label className="visually-hidden" htmlFor={id}>{label}, line {index + 1}</label>
              <input className={(key === "description" ? "" : "fig item-number") + (changed ? " is-edited" : "")} id={id} value={value}
                inputMode={key === "description" ? undefined : "decimal"} onChange={(event) => changeItem(index, key, event.target.value)}
                aria-invalid={issue ? true : undefined} aria-describedby={issue ? id + "-error" : undefined}
                data-source-line={key === "description" ? sourceId : undefined}
                onFocus={() => onActive(sourceId)} onBlur={(event) => { onActive(null); finishItem(index, key, event); }} />
              {issue && <small className="error-text" id={id + "-error"}>{issue}</small>}
            </td>;
          })}
          <td><Button className="remove-line" variant="quiet" aria-label={"Remove line " + (index + 1)} onClick={() => {
            remove(index); setIssues((old) => old.filter((issue) => !issue.id.startsWith(inputId("item-"))));
            requestAnimationFrame(() => (document.getElementById(itemId(index, "description")) ?? document.getElementById(inputId("add-line")))?.focus());
          }}>×</Button></td>
        </tr>; })}</tbody>
      </table></div> : <p className="meta">No line items yet.</p>}
      <Button className="add" id={inputId("add-line")} onClick={() => {
        const index = fields.length;
        append({ ...emptyLine, position: -1 }, { shouldFocus: false });
        requestAnimationFrame(() => document.getElementById(itemId(index, "description"))?.focus());
      }}>Add a line</Button>
    </fieldset>
    <div className="actions">
      {error && <p className="error-text action-error" role="alert">{error}</p>}
      <Button variant="primary" type="submit" disabled={busy}>{busy ? "Working…" : "Save to journal"}</Button>
      <Button onClick={onRead} disabled={busy}>Read again</Button>
      <Button variant="quiet" onClick={onDelete} disabled={busy}>Delete</Button>
    </div>
  </form>;
}
