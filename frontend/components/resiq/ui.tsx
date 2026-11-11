import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import type { ReceiptStatus } from "@/lib/types";

type Variant = "primary" | "secondary" | "quiet" | "on-dark";
type Tone = "check" | "ok" | "error" | "busy";
const buttonClass = (variant: Variant, className = "") => "btn btn--" + variant + " " + className;

export function Button({ variant = "secondary", className, type = "button", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return <button {...props} type={type} data-variant={variant} className={buttonClass(variant, className)} />;
}

export function ButtonLink({ variant = "secondary", className, href, children }: { variant?: Variant; className?: string; href: string; children: ReactNode }) {
  return <Link href={href} data-variant={variant} className={buttonClass(variant, className)}>{children}</Link>;
}

export function Chip({ tone, children }: { tone: Tone; children: ReactNode }) {
  return <span className={"chip chip--" + tone}>{children}</span>;
}

const statuses: Record<ReceiptStatus, [Tone, string]> = {
  queued: ["busy", "Queued"], processing: ["busy", "Reading"], needs_review: ["check", "Needs review"],
  verified: ["ok", "Verified"], failed: ["error", "Could not read"],
};

export function StatusChip({ status }: { status: ReceiptStatus }) {
  const [tone, label] = statuses[status];
  return <Chip tone={tone}>{label}</Chip>;
}

export function TopBar({ current }: { current?: "receipts" | "journal" }) {
  return <header className="shell-header"><div className="topbar app-container">
    <Link className="wordmark" href="/">Resiq</Link>
    <nav aria-label="Main">
      <Link href="/receipts" aria-current={current === "receipts" ? "page" : undefined}>Receipts</Link>
      <Link href="/journal" aria-current={current === "journal" ? "page" : undefined}>Journal</Link>
    </nav>
    <ButtonLink href="/upload">Upload <span className="wide-label">receipts</span></ButtonLink>
  </div></header>;
}

export function Skeleton({ label = "Loading…" }: { label?: string }) {
  return <div className="skeleton-group" role="status"><p>{label}</p>{[0, 1, 2].map((row) => <span className="skeleton" key={row} aria-hidden="true" />)}</div>;
}

export function ErrorNotice({ children, retry }: { children: ReactNode; retry?: () => void }) {
  return <div className="notice notice--error" role="alert"><p>{children}</p>{retry && <Button onClick={retry}>Try again</Button>}</div>;
}

export function ClosingRule() {
  return <span className="closing" aria-hidden="true" />;
}
