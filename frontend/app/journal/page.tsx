import type { Metadata } from "next";
import { Suspense } from "react";
import { JournalScreen } from "@/components/journal-screen";
import { Skeleton, TopBar } from "@/components/resiq/ui";

export const metadata: Metadata = { title: "Journal" };

export default function Page() {
  return <Suspense fallback={<><TopBar current="journal" /><main id="main" className="app-container screen"><Skeleton label="Opening journal…" /></main></>}>
    <JournalScreen />
  </Suspense>;
}
