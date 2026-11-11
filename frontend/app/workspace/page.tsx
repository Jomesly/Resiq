import type { Metadata } from "next";
import { WorkspaceScreen } from "@/components/workspace-screen";

export const metadata: Metadata = { title: "Workspace recovery", robots: { index: false } };
export default function Page() { return <WorkspaceScreen />; }
