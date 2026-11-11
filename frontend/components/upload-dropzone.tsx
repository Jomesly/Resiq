"use client";

import { useRef, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useDropzone, type FileRejection } from "react-dropzone";
import { API_BASE, apiFetch } from "@/lib/api";
import { storedToken } from "@/lib/workspace";
import { errorText, getReceipt, isReading, uploadReceipt } from "@/lib/receipts";
import type { ReceiptStatus } from "@/lib/types";
import { Button, ButtonLink, Chip, StatusChip } from "./resiq/ui";
import { ReceiptImage } from "./receipt-image";

type Row = { key: number; file: File; progress: number; id?: string; status?: ReceiptStatus; error?: string; sent?: boolean };
type SampleKey = "kapihan" | "mercury" | "petron";
const MAX_SIZE = 10 * 1024 * 1024;
const types = {
  "image/jpeg": [".jpg", ".jpeg"], "image/png": [".png"], "image/webp": [".webp"],
  "image/heic": [".heic"], "image/heif": [".heif"],
};
const uploadError = (rejection: FileRejection) => rejection.errors.some((error) => error.code === "file-too-large")
  ? "This photo is too large: use one under 10 MB."
  : "Only JPG, PNG, WebP, or HEIC images.";

function UploadRow({ row }: { row: Row }) {
  const receipt = useQuery({
    queryKey: ["receipt", row.id], queryFn: () => getReceipt(row.id!),
    enabled: Boolean(row.id), refetchInterval: (query) => isReading(query.state.data?.status) ? 850 : false,
  });
  const status = receipt.data?.status ?? row.status;
  return <li className="upload-row">
    {receipt.data?.thumbnail_url ? <ReceiptImage className="thumbnail" src={receipt.data.thumbnail_url} alt="" /> : <span className="thumbnail thumbnail--blank" aria-hidden="true" />}
    <div className="upload-row__details">
      <strong>{row.file.name}</strong>
      <small className="meta">{new Intl.NumberFormat("en-PH", { maximumFractionDigits: 1 }).format(row.file.size / 1024)} KB</small>
      {!row.error && <progress value={row.progress} max={100} aria-label={"Upload progress for " + row.file.name} aria-valuenow={row.progress} />}
      {row.error && <small className="error-text" role="alert">{row.error}</small>}
    </div>
    <div className="upload-row__state" aria-live="polite">
      {row.error ? <Chip tone="error">Not uploaded</Chip> : status ? <StatusChip status={status} /> : <Chip tone="busy">{row.sent ? "Uploading" : "Waiting"}</Chip>}
    </div>
    {row.id && <ButtonLink href={"/receipts/" + row.id}>Open<span className="visually-hidden"> {row.file.name}</span></ButtonLink>}
  </li>;
}

export function UploadDropzone({ Hero, className = "" }: {
  Hero?: (controls: { open: () => void; trySample: (key?: SampleKey) => void; sampleBusy: boolean }) => ReactNode;
  className?: string;
}) {
  const router = useRouter();
  const client = useQueryClient();
  const [rows, setRows] = useState<Row[]>([]);
  const [sampleBusy, setSampleBusy] = useState(false);
  const [sampleError, setSampleError] = useState("");
  const sequence = useRef(0);
  const pending = useRef<{ key: number; file: File; openAfter: boolean }[]>([]);
  const active = useRef(0);
  const workspace = useQuery({ queryKey: ["workspace"], queryFn: () => storedToken(API_BASE) ? apiFetch<{ recovery_enabled: boolean; recovery_required: boolean }>("/api/workspace") : Promise.resolve(null), enabled: Boolean(API_BASE) });
  const needsRecovery = workspace.data?.recovery_required && !workspace.data.recovery_enabled;

  function change(key: number, fields: Partial<Row>) {
    setRows((old) => old.map((row) => row.key === key ? { ...row, ...fields } : row));
  }

  function drain() {
    while (active.current < 3 && pending.current.length) {
      const { key, file, openAfter } = pending.current.shift()!;
      active.current++;
      change(key, { sent: true });
      void uploadReceipt(file, (progress) => change(key, { progress })).then(({ id, status }) => {
        change(key, { id, status });
        void client.invalidateQueries({ queryKey: ["receipts"] });
        if (openAfter) router.push("/receipts/" + id);
      }).catch((error) => {
        change(key, { error: errorText(error) });
        if (openAfter) setSampleError(errorText(error));
      }).finally(() => {
        active.current--;
        if (openAfter) setSampleBusy(false);
        drain();
      });
    }
  }

  function enqueue(accepted: File[], rejected: FileRejection[], openAfter = false) {
    if (needsRecovery) { router.push("/workspace"); setSampleBusy(false); return; }
    const next: Row[] = [
      ...accepted.map((file) => ({ key: ++sequence.current, file, progress: 0, error: file.size ? undefined : "This photo is empty. Choose another file." })),
      ...rejected.map((rejection) => ({ key: ++sequence.current, file: rejection.file, progress: 0, error: uploadError(rejection) })),
    ];
    setRows((old) => [...old, ...next]);
    pending.current.push(...next.filter((row) => !row.error).map(({ file, key }) => ({ file, key, openAfter })));
    drain();
  }

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    accept: types, maxSize: MAX_SIZE, multiple: true, noClick: true, noKeyboard: true,
    onDrop: (accepted, rejected) => enqueue(accepted, rejected),
  });

  function trySample(key: SampleKey = "kapihan") {
    if (sampleBusy) return;
    setSampleBusy(true);
    setSampleError("");
    fetch("/samples/" + key + ".png").then(async (res) => {
      if (!res.ok) throw new Error("The sample could not load. Try again.");
      const blob = await res.blob();
      if (!blob.size) throw new Error("The sample could not load. Try again.");
      enqueue([new File([blob], key + ".png", { type: "image/png" })], [], true);
    }).catch((error) => {
      setSampleError(errorText(error));
      setSampleBusy(false);
    });
  }

  return <div {...getRootProps({ className: "upload-surface " + className + (isDragActive ? " is-dragging" : "") })}>
    {API_BASE && !workspace.data?.recovery_enabled && <div className="notice"><p>{needsRecovery ? "Save a recovery code before uploading your receipts." : "Protect your receipts with a recovery code so you can open them from another browser."}</p><ButtonLink href="/workspace">Set up workspace recovery</ButtonLink></div>}
    <input {...getInputProps({ "aria-label": "Choose receipt photos" })} />
    {Hero ? <Hero open={open} trySample={trySample} sampleBusy={sampleBusy} /> : <div className="dropzone">
      <h2>Drop your receipt photos here</h2>
      <p>JPG, PNG, WebP or HEIC. Up to 10 MB each.</p>
      <Button variant="primary" onClick={open}>Choose photos</Button>
    </div>}
    {!Hero && <div className="sample-picker">
      <p>{API_BASE ? "Try a sample receipt." : "In this demo, samples are read automatically. You can enter your own receipts by hand."}</p>
      <div className="button-group">
        <Button disabled={sampleBusy} onClick={() => trySample()}>Kapihan sa Kanto</Button>
        <Button disabled={sampleBusy} onClick={() => trySample("mercury")}>Mercury Drug</Button>
        <Button disabled={sampleBusy} onClick={() => trySample("petron")}>Petron Katipunan</Button>
      </div>
    </div>}
    {sampleError && <p className="notice notice--error" role="alert">{sampleError}</p>}
    {rows.length > 0 && <ul className="upload-list" aria-label="Receipt uploads">{rows.map((row) => <UploadRow key={row.key} row={row} />)}</ul>}
  </div>;
}
