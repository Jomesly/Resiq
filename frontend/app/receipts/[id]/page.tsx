import { Suspense } from "react";
import type { Metadata } from "next";
import { ReceiptReview } from "@/components/receipt-review";
import { Skeleton, TopBar } from "@/components/resiq/ui";

export const metadata: Metadata = { title: "Review receipt" };

async function Review({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ReceiptReview key={id} id={id} />;
}

export default function Page({ params }: { params: Promise<{ id: string }> }) {
  return <Suspense fallback={<><TopBar current="receipts" /><main id="main" className="app-container screen"><Skeleton label="Opening receipt…" /></main></>}>
    <Review params={params} />
  </Suspense>;
}
