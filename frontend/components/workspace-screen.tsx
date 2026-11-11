"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { API_BASE, apiFetch } from "@/lib/api";
import { setToken, storedToken } from "@/lib/workspace";
import { Button, ButtonLink, ErrorNotice, TopBar } from "./resiq/ui";

type Info = { recovery_enabled: boolean; recovery_required: boolean };

export function WorkspaceScreen() {
  const client = useQueryClient();
  const [code, setCode] = useState("");
  const [saved, setSaved] = useState(false);
  const [restore, setRestore] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const info = useQuery({ queryKey: ["workspace"], queryFn: () => storedToken(API_BASE)
    ? apiFetch<Info>("/api/workspace") : Promise.resolve(null), enabled: Boolean(API_BASE), retry: false });

  async function perform(action: () => Promise<void>) {
    setBusy(true); setError(""); setMessage("");
    try { await action(); } catch (err) { setError(err instanceof Error ? err.message : "Please try again."); }
    finally { setBusy(false); }
  }

  function download() {
    const url = URL.createObjectURL(new Blob([
      `Resiq workspace recovery\nServer: ${API_BASE}\nRecovery code: ${code}\n\nKeep this file in a password manager or another safe place. Anyone with this code can access your receipts. Recover from ${window.location.origin}/workspace.\n`,
    ], { type: "text/plain" }));
    const link = document.createElement("a"); link.href = url; link.download = "resiq-recovery.txt"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <><TopBar /><main id="main" className="app-container screen workspace-screen">
    <div className="screen-heading"><div><h1>Your workspace</h1><p>Keep access to your receipts when you change browsers or devices.</p></div></div>
    {!API_BASE ? <p>Workspace recovery is available when connected to the receipt service. This is the offline demo.</p> : <>
      {(error || info.error) && <ErrorNotice>{error || info.error?.message}</ErrorNotice>}
      {message && <p className="notice" role="status">{message}</p>}
      <section className="workspace-panel" aria-labelledby="protect-workspace">
        <h2 id="protect-workspace">Save a recovery code</h2>
        <p>{info.data?.recovery_enabled ? "Recovery is enabled. Keep your saved code safe." : "Your browser holds your access key. Save a separate recovery code before relying on this workspace."}</p>
        <p>Anyone with the recovery code can access your receipts. Store it in a password manager or another safe place outside this browser.</p>
        <Button disabled={busy} onClick={() => void perform(async () => {
          const result = await apiFetch<{ recovery_code: string }>("/api/workspace/recovery", { method: "POST" });
          setCode(result.recovery_code); setSaved(false);
        })}>{info.data?.recovery_enabled ? "Prepare replacement code" : "Create recovery code"}</Button>
        {code && <div className="workspace-code">
          <label htmlFor="new-recovery-code">Your new recovery code</label>
          <input id="new-recovery-code" readOnly value={code} autoComplete="off" spellCheck={false} />
          <Button onClick={download}>Download recovery file</Button>
          <label className="recovery-confirm"><input type="checkbox" checked={saved} onChange={(event) => setSaved(event.target.checked)} /> I saved this code outside this browser.</label>
          <Button variant="primary" disabled={busy || !saved} onClick={() => void perform(async () => {
            await apiFetch("/api/workspace/recovery/confirm", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ recovery_code: code }) });
            setCode(""); setSaved(false); await client.invalidateQueries({ queryKey: ["workspace"] });
            setMessage("Recovery is enabled. Any previous recovery code has been replaced.");
          })}>Enable saved code</Button>
          <p>The new code only becomes active after confirmation. Keep this page open until you confirm.</p>
        </div>}
      </section>
      <section className="workspace-panel" aria-labelledby="recover-workspace">
        <h2 id="recover-workspace">Recover an existing workspace</h2>
        <p>Enter your saved code to open that workspace here. This signs out its other browsers and devices.</p>
        <form onSubmit={(event) => { event.preventDefault(); void perform(async () => {
          const response = await fetch(API_BASE + "/api/workspaces/recover", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ recovery_code: restore.trim() }) });
          if (!response.ok) throw new Error(response.status === 429 ? "Too many attempts. Try again in a minute." : "Recovery failed. Check the code and server, then try again.");
          const result = await response.json() as { token: string };
          setToken(API_BASE, result.token); setRestore(""); setCode(""); client.clear();
          // A workspace switch must discard cached pages and unsaved forms from the old identity.
          // eslint-disable-next-line @next/next/no-location-assign-relative-destination
          window.location.assign("/receipts");
        }); }}>
          <div className="field"><label htmlFor="restore-code">Saved recovery code</label><input id="restore-code" type="password" autoComplete="off" required minLength={43} maxLength={100} value={restore} onChange={(event) => setRestore(event.target.value)} /></div>
          <Button type="submit" disabled={busy}>Recover and sign out other devices</Button>
        </form>
      </section>
      {info.data?.recovery_enabled && <section className="workspace-panel" aria-labelledby="rotate-workspace">
        <h2 id="rotate-workspace">Replace browser access</h2><p>Keep this browser signed in and sign out other devices. Your recovery code stays valid.</p>
        <Button disabled={busy} onClick={() => void perform(async () => {
          const result = await apiFetch<{ token: string }>("/api/workspace/rotate", { method: "POST" });
          setToken(API_BASE, result.token); client.clear(); setMessage("Access replaced. Other devices have been signed out.");
        })}>Sign out other devices</Button>
      </section>}
      <ButtonLink href="/upload" variant="primary">Continue to receipts</ButtonLink>
    </>}
  </main></>;
}
