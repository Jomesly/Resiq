import type { Metadata } from "next";
import { TopBar } from "@/components/resiq/ui";
import { UploadDropzone } from "@/components/upload-dropzone";

export const metadata: Metadata = { title: "Upload receipts" };

export default function Page() {
  return <><TopBar /><main id="main" className="app-container screen upload-screen">
    <div className="screen-heading"><div><h1>Upload receipts</h1><p>Start with a photo of each receipt.</p></div></div>
    <UploadDropzone />
  </main></>;
}
