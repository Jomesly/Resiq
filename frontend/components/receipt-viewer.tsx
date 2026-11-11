"use client";

import { useRef, useState, type KeyboardEvent } from "react";
import { formatDate } from "@/lib/format";
import type { Box, ReceiptDetail, StageName } from "@/lib/types";
import { ReceiptImage } from "./receipt-image";
import { Button } from "./resiq/ui";

export type FieldBox = { id: string; label: string; box: Box };
const stageLabels: [StageName, string][] = [["original", "As taken"], ["warped", "Straightened"], ["enhanced", "Read"]];

export function ReceiptViewer({ detail, boxes, activeId, onBoxClick }: { detail: ReceiptDetail; boxes: FieldBox[]; activeId: string | null; onBoxClick: (id: string) => void }) {
  const stages = {
    ...detail.stages,
    original: detail.stages.original ?? detail.image?.original_url,
    enhanced: (detail.extraction ? detail.image?.processed_url : undefined) ?? detail.stages.enhanced,
  };
  const available = stageLabels.filter(([id]) => stages[id]);
  const [choice, setChoice] = useState<StageName>("enhanced");
  const [zoom, setZoom] = useState(1);
  const [showText, setShowText] = useState(false);
  const [badSrc, setBadSrc] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const stage = stages[choice] ? choice : available[0]?.[0];
  const src = stage ? stages[stage] : undefined;
  const width = detail.image?.width ?? 0, height = detail.image?.height ?? 0;
  const showBoxes = stage === "enhanced" && width > 0 && height > 0;
  const tabs = useRef<Record<string, HTMLButtonElement | null>>({});
  const tabId = (id: StageName) => "stage-tab-" + detail.id + "-" + id;
  const panelId = (id: StageName) => "stage-panel-" + detail.id + "-" + id;
  const isSample = detail.extraction?.engine_version === "resiq-sample-v1";
  const alt = "Receipt" + (detail.merchant ? " from " + detail.merchant : " photo") + (detail.receipt_date ? ", " + formatDate(detail.receipt_date) : "");

  function tabKeys(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const last = available.length - 1;
    const next = event.key === "ArrowLeft" ? (index + last) % available.length :
      event.key === "ArrowRight" ? (index + 1) % available.length : event.key === "Home" ? 0 : event.key === "End" ? last : -1;
    if (next < 0) return;
    event.preventDefault();
    const id = available[next][0];
    setChoice(id);
    tabs.current[id]?.focus();
  }

  return <aside className="viewer" aria-label="Receipt photo">
    {src && <div className="viewer__bar">
      <div className="tabs" role="tablist" aria-label="Receipt image stage">
        {available.map(([id, label], index) => <button key={id} ref={(node) => { tabs.current[id] = node; }} type="button"
          id={tabId(id)} role="tab" aria-selected={stage === id} aria-controls={panelId(id)}
          tabIndex={stage === id ? 0 : -1} onClick={() => setChoice(id)} onKeyDown={(event) => tabKeys(event, index)}>{label}</button>)}
      </div>
      <div className="tools">
        <Button variant="on-dark" aria-pressed={showText && showBoxes} disabled={!showBoxes || !detail.ocr_lines.length} onClick={() => setShowText((value) => !value)}>Show all text</Button>
        <Button variant="on-dark" className="zoom-btn" aria-label="Zoom out" disabled={zoom <= 1} onClick={() => setZoom((value) => Math.max(1, value - .5))}>−</Button>
        <Button variant="on-dark" className="zoom-btn" aria-label="Zoom in" disabled={zoom >= 4} onClick={() => setZoom((value) => Math.min(4, value + .5))}>+</Button>
      </div>
    </div>}
    {detail.quality?.warnings.map((warning) => <p className="viewer__note" key={warning}>{warning}</p>)}
    {available.filter(([id]) => id !== stage).map(([id]) => <div key={id} role="tabpanel" hidden id={panelId(id)} aria-labelledby={tabId(id)} />)}
    <div className="stage" id={stage ? panelId(stage) : undefined} role={stage ? "tabpanel" : undefined}
      aria-labelledby={stage ? tabId(stage) : undefined} tabIndex={0}>
      {src && badSrc !== src ? <div className="stage__inner" style={{ "--photo-zoom": zoom } as React.CSSProperties}>
        <div className={"photo" + (isSample && stage === "original" ? " photo--sample-original" : "")}>
          <ReceiptImage src={src} alt={alt} onError={() => setBadSrc(src)} />
          {showBoxes && <>
            <svg aria-hidden="true" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
              {showText && detail.ocr_lines.map(({ box: [x, y, x1, y1] }, index) => <rect key={index} className="ocr-box" x={x} y={y} width={x1 - x} height={y1 - y} />)}
              {boxes.map(({ id, box: [x, y, x1, y1] }) => <rect key={id} className={"box" + (id === (hovered ?? activeId) ? " is-active" : "")}
                x={x} y={y} width={x1 - x} height={y1 - y} />)}
            </svg>
            {boxes.map(({ id, label, box: [x, y, x1, y1] }) => <button key={id} type="button" className="box-hit" aria-label={"Focus " + label}
              style={{ left: x / width * 100 + "%", top: y / height * 100 + "%", width: (x1 - x) / width * 100 + "%", height: (y1 - y) / height * 100 + "%" }}
              onFocus={() => setHovered(id)} onBlur={() => setHovered(null)} onPointerEnter={() => setHovered(id)} onPointerLeave={() => setHovered(null)}
              onClick={() => onBoxClick(id)} />)}
          </>}
        </div>
      </div> : <p className="viewer__empty">{src ? "This browser could not display the receipt photo." : "No photo is available."}</p>}
    </div>
  </aside>;
}
