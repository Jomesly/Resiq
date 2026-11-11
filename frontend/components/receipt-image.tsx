"use client";

import { useEffect, useState } from "react";
import { isStoredImage, readImage } from "@/lib/mock/images";
import { receiptImageUrl } from "@/lib/receipts";

export function ReceiptImage({ src, alt, className, onError }: { src: string; alt: string; className?: string; onError?: () => void }) {
  const [image, setImage] = useState<{ source: string; url: string | null }>();
  const stored = isStoredImage(src);
  useEffect(() => {
    if (!stored) return;
    let canceled = false;
    let objectUrl: string | undefined;
    readImage(src).then((blob) => {
      if (canceled) return;
      objectUrl = blob && URL.createObjectURL(blob);
      setImage({ source: src, url: objectUrl ?? null });
    }).catch(() => {
      if (!canceled) setImage({ source: src, url: null });
    });
    return () => {
      canceled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [src, stored]);
  const url = stored ? (image?.source === src ? image.url : undefined) : receiptImageUrl(src);
  if (url === null) return alt ? <span className="image-placeholder">Preview unavailable</span> : null;
  if (!url) return null;
  // Signed URLs and browser-local blob URLs are used directly.
  // eslint-disable-next-line @next/next/no-img-element
  return <img className={className} src={url} alt={alt} onError={onError} />;
}
