import type { Metadata } from "next";
import { Suspense } from "react";
import { ReceiptsList } from "@/components/receipts-list";
import { Skeleton, TopBar } from "@/components/resiq/ui";

export const metadata: Metadata = { title: "Receipts" };

export default function Page() {
  return <Suspense fallback={<><TopBar current="receipts" /><main id="main" className="app-container screen"><Skeleton label="Loading receipts…" /></main></>}>
    <ReceiptsList />
  </Suspense>;
}
