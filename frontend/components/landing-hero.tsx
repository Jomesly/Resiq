"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { Button } from "./resiq/ui";
import { UploadDropzone } from "./upload-dropzone";

function HeroEntry() {
  const figure = useRef<HTMLElement>(null);
  const photo = useRef<HTMLImageElement>(null);
  const row = useRef<HTMLTableRowElement>(null);
  const [path, setPath] = useState("");
  useEffect(() => {
    const elements = [figure.current, photo.current, row.current] as const;
    const [fig, img, added] = elements;
    if (!fig || !img || !added) return;
    const draw = () => {
      const f = fig.getBoundingClientRect(), a = img.getBoundingClientRect(), b = added.getBoundingClientRect();
      const x1 = a.right - f.left + 4, y1 = a.top + a.height * 0.666 - f.top;
      const x2 = b.left - f.left - 2, y2 = b.top + b.height / 2 - f.top;
      setPath("M" + x1 + " " + y1 + " C " + (x1 + 24) + " " + y1 + ", " + (x2 - 24) + " " + y2 + ", " + x2 + " " + y2);
    };
    const observer = new ResizeObserver(draw);
    elements.forEach((element) => { if (element) observer.observe(element); });
    return () => observer.disconnect();
  }, []);

  return <figure className="entry" ref={figure}>
    <Image priority unoptimized className="receipt" ref={photo} src="/samples/hero-receipt.png" width={536} height={736}
      alt="Sample receipt from Kapihan sa Kanto, 9 November 2026. Total 135 pesos, VAT 14.46." />
    <div className="book"><table>
      <caption className="visually-hidden">Sample journal, November 2026</caption>
      <thead><tr><th scope="col">Date</th><th scope="col">Particulars</th><th scope="col" className="num">Amount</th></tr></thead>
      <tbody>
        <tr><td>Nov 4</td><td>Mercury Drug</td><td className="num">612.75</td></tr>
        <tr><td>Nov 6</td><td>Converge</td><td className="num">1,500.00</td></tr>
        <tr><td>Nov 7</td><td>National Book Store</td><td className="num">450.00</td></tr>
        <tr className="new" ref={row}><td>Nov 9</td><td>Kapihan sa Kanto</td><td className="num">135.00</td></tr>
        <tr className="total"><td colSpan={2}>Balanced</td><td className="num">2,697.75</td></tr>
      </tbody>
    </table></div>
    <svg className="connector-svg" aria-hidden="true"><path d={path} /></svg>
  </figure>;
}

function Hero({ open, trySample, sampleBusy }: { open: () => void; trySample: () => void; sampleBusy: boolean }) {
  return <section className="container hero" aria-labelledby="hero-title">
      <div>
        <h1 id="hero-title">From resibo to columnar book.</h1>
        <p className="hero__lede">Photograph a receipt. Resiq enters it and checks the VAT.</p>
        <div className="hero__actions">
          <Button variant="primary" onClick={open}>Upload a receipt</Button>
          <Button onClick={() => trySample()} disabled={sampleBusy}>{sampleBusy ? "Opening sample…" : "Try a sample receipt"}</Button>
        </div>
      </div>
      <HeroEntry />
    </section>;
}

export function LandingHero() {
  return <UploadDropzone className="landing-drop" Hero={Hero} />;
}
