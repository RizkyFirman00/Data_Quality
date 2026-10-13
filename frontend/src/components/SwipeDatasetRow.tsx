import { useRef, useState, type PointerEvent } from "react";
import { Link } from "react-router-dom";
import { ChevronRightIcon, TrashIcon } from "../icons";
import type { DatasetSummary } from "../types";
import { datasetAssessmentLabel, datasetAssessmentTone } from "../presentation";
import { datasetSwipeOutcome } from "../datasetGestures";

const date = (value: string) => new Intl.DateTimeFormat("id-ID", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));

export default function SwipeDatasetRow({ item, selected, isAdmin, onSelect, onDelete }: {
  item: DatasetSummary; selected: boolean; isAdmin: boolean; onSelect: () => void; onDelete: () => void;
}) {
  const [offset, setOffset] = useState(0);
  const [dragging, setDragging] = useState(false);
  const gesture = useRef<{ x: number; y: number; initial: number; distance: number; horizontal: boolean } | null>(null);
  const ignoreClickUntil = useRef(0);
  const processing = item.status === "PROCESSING";
  const start = (event: PointerEvent<HTMLDivElement>) => {
    if (processing || !event.isPrimary || event.button !== 0 || (event.target as HTMLElement).closest("button,input,label")) return;
    gesture.current = { x: event.clientX, y: event.clientY, initial: offset, distance: 0, horizontal: false };
  };
  const move = (event: PointerEvent<HTMLDivElement>) => {
    const current = gesture.current;
    if (!current) return;
    const dx = event.clientX - current.x;
    const dy = event.clientY - current.y;
    if (!current.horizontal) {
      if (Math.abs(dy) > 10 && Math.abs(dy) > Math.abs(dx)) { gesture.current = null; return; }
      if (Math.abs(dx) < 10 || Math.abs(dx) <= Math.abs(dy)) return;
      current.horizontal = true;
      event.currentTarget.setPointerCapture(event.pointerId);
      setDragging(true);
    }
    current.distance = Math.min(220, Math.max(0, current.initial - dx));
    setOffset(current.distance);
  };
  const finish = (event: PointerEvent<HTMLDivElement>, cancelled = false) => {
    const current = gesture.current;
    gesture.current = null;
    setDragging(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    if (!current?.horizontal) return;
    ignoreClickUntil.current = Date.now() + 450;
    const outcome = datasetSwipeOutcome(current.distance, cancelled);
    if (outcome === "confirm") { setOffset(0); onDelete(); }
    else setOffset(outcome === "reveal" ? 88 : 0);
  };

  return <div className={`dataset-swipe-shell${selected ? " selected" : ""}${offset ? " revealed" : ""}`} role="row">
    {offset > 0 && <button className="dataset-swipe-delete" type="button" disabled={processing} onClick={() => { setOffset(0); onDelete(); }}><TrashIcon size={18} />Hapus</button>}
    <div className={`dataset-swipe-content${dragging ? " dragging" : ""}`} style={{ transform: `translateX(-${offset}px)` }}
      onPointerDown={start} onPointerMove={move} onPointerUp={(event) => finish(event)} onPointerCancel={(event) => finish(event, true)}
      onClickCapture={(event) => { if (Date.now() < ignoreClickUntil.current) { event.preventDefault(); event.stopPropagation(); } }}>
      <label className="dataset-select-cell" role="cell"><input type="checkbox" checked={selected} disabled={processing} onChange={onSelect} aria-label={`Pilih ${item.original_filename}`} /></label>
      <Link className="dataset-table-row" to={`/datasets/${item.id}`} draggable={false} onDragStart={(event) => event.preventDefault()} aria-describedby="dataset-swipe-keyboard-help" onKeyDown={(event) => {
        if (processing) return;
        if (event.key === "ArrowLeft") { event.preventDefault(); setOffset(88); }
        if (event.key === "ArrowRight" || event.key === "Escape") { event.preventDefault(); setOffset(0); }
      }}>
        <span role="cell" className="dataset-identity"><strong>{item.original_filename}</strong><small>{isAdmin ? `${item.owner_display_name || "Dataset lama tanpa pemilik"} · ` : ""}{item.source_type === "backoffice_api" ? "Backoffice" : "Unggahan file"}</small></span>
        <span role="cell"><b className="file-chip">{item.file_type.toUpperCase()}</b></span>
        <span role="cell" data-label="Dimensi">{item.row_count.toLocaleString("id-ID")} × {item.column_count}</span>
        <span role="cell" data-label="Temuan">{item.finding_count.toLocaleString("id-ID")}</span>
        <time role="cell" data-label="Diunggah">{date(item.created_at)}</time>
        <span role="cell"><b className={`status-chip ${datasetAssessmentTone(item)}`}>{datasetAssessmentLabel(item)}</b></span>
        <ChevronRightIcon className="row-chevron" size={18} />
      </Link>
    </div>
  </div>;
}
