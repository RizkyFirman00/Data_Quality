import { Fragment, useEffect, useMemo, useState } from "react";
import { listFindings } from "../api";
import { ArrowLeftIcon, ArrowRightIcon, ChevronDownIcon } from "../icons";
import { formatIssueLabel, type DatasetDetail, type Finding, type FindingPage } from "../types";
import { displayOriginalValue as displayValue, isPotentialIssue } from "../presentation";

const isReview = (finding: Finding) => isPotentialIssue(finding.issue_type);
const hoverReason = (finding: Finding) => finding.issue_type === "INVALID_CASE" ? "Masih menggunakan huruf kecil" : finding.issue_type === "MISSING_VALUE" ? "Nilai belum terisi" : finding.issue_type === "INVALID_PLACEHOLDER" ? "Tanda '-' tidak valid sebagai nilai kosong" : finding.issue_type === "STATISTICAL_ANOMALY" ? finding.evidence : `${formatIssueLabel(finding.issue_type)}: ${finding.evidence}`;

export default function FindingsDataTable({ dataset, onOpenSourceRow }: {
  dataset: DatasetDetail;
  onOpenSourceRow: (row: number, findingId: string) => void;
}) {
  const [result, setResult] = useState<FindingPage | null>(null);
  const [page, setPage] = useState(1);
  const [kind, setKind] = useState("all");
  const [query, setQuery] = useState("");
  const executionMetadata = dataset.source_metadata.quality_checks;
  const execution = executionMetadata && typeof executionMetadata === "object" ? executionMetadata as Record<string, unknown> : null;
  const executedChecks = Array.isArray(execution?.executed) ? execution.executed.filter((check): check is string => typeof check === "string") : null;
  const skippedChecks = Array.isArray(execution?.skipped) ? execution.skipped.length : null;
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [selected, setSelected] = useState<{ row: number; column: string | null } | null>(null);
  const [sort, setSort] = useState<{ column: string; direction: "asc" | "desc" }>({ column: "_source_row", direction: "asc" });
  const [tooltip, setTooltip] = useState<{ id: string; text: string; top: number; left: number } | null>(null);
  const pageSize = 20;
  const columns = dataset.column_profiles.map((column) => column.display_name);
  const summary = useMemo(() => {
    const required = dataset.findings.filter((finding) => !isReview(finding));
    const review = dataset.findings.filter(isReview);
    return { rows: new Set(dataset.findings.map((finding) => finding.row)).size, required: required.length, review: review.length };
  }, [dataset.findings]);

  useEffect(() => {
    const timer = window.setTimeout(() => { setSearch(query.trim()); setPage(1); setSelected(null); }, 300);
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setTooltip(null);
    listFindings(dataset.id, { page, pageSize, groupByRow: true, search, assessmentKind: kind === "all" ? undefined : kind, sortBy: sort.column, sortDirection: sort.direction })
      .then((data) => { if (!cancelled) setResult(data); })
      .catch((reason) => { if (!cancelled) setError(reason instanceof Error ? reason.message : "Baris temuan tidak dapat dimuat."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [dataset.id, page, kind, search, retry, sort]);

  const changeSort = (column: string) => {
    setSort((current) => ({ column, direction: current.column === column && current.direction === "asc" ? "desc" : "asc" }));
    setPage(1);
    setSelected(null);
  };
  const showTooltip = (target: HTMLButtonElement, id: string, text: string) => {
    const box = target.getBoundingClientRect();
    setTooltip({ id, text, top: Math.max(12, box.bottom + 100 > window.innerHeight ? box.top - 90 : box.bottom + 8), left: Math.max(12, Math.min(box.left, window.innerWidth - 292)) });
  };
  useEffect(() => {
    const hideTooltip = () => setTooltip(null);
    window.addEventListener("scroll", hideTooltip, true);
    window.addEventListener("resize", hideTooltip);
    return () => { window.removeEventListener("scroll", hideTooltip, true); window.removeEventListener("resize", hideTooltip); };
  }, []);
  const sortHeader = (column: string, label: string) => <th scope="col" key={column} className={column === "_source_row" ? "affected-source-column" : ""} aria-sort={sort.column === column ? sort.direction === "asc" ? "ascending" : "descending" : "none"}><button type="button" className="affected-column-sort" title={column === "_source_row" ? label : column} onClick={() => changeSort(column)}><span>{label}</span><span className="affected-sort-direction" aria-hidden="true">{sort.column === column ? sort.direction === "asc" ? "↑" : "↓" : "↕"}</span></button></th>;

  const chooseRow = (row: number, column: string | null = null) => {
    setSelected((current) => current?.row === row && current.column === column ? null : { row, column });
  };
  const pageCount = Math.max(1, Math.ceil((result?.total_rows || 0) / pageSize));

  return <section className="affected-data-view" role="tabpanel" aria-label="Temuan kualitas dalam data">
    <div className="affected-data-summary"><strong>{summary.rows.toLocaleString("id-ID")} baris terdampak <span>dari {dataset.row_count.toLocaleString("id-ID")}</span></strong><span className="cell-legend required">! {summary.required.toLocaleString("id-ID")} ketidaksesuaian</span><span className="cell-legend review">? {summary.review.toLocaleString("id-ID")} potensi masalah</span></div>
    <div className="affected-data-toolbar"><div className="affected-data-filters" aria-label="Filter temuan">{[["all", "Semua temuan"], ["required", "Ketidaksesuaian"], ["review", "Potensi anomali / semantik"]].map(([key, label]) => <button type="button" key={key} aria-pressed={kind === key} onClick={() => { setKind(key); setPage(1); setSelected(null); }}>{label}</button>)}</div><label className="affected-data-search"><span className="sr-only">Cari nilai atau wilayah pada baris temuan</span><input name="affected-row-search" type="search" placeholder="Cari wilayah atau nilai…" value={query} onChange={(event) => setQuery(event.target.value)} /></label></div>
    <p className="affected-data-hint">Klik sel bertanda untuk melihat alasannya, atau nomor baris untuk seluruh temuan. Nilai yang tampil adalah nilai asli.</p>
    {error ? <div className="feedback error inset" role="alert"><p>{error}</p><button type="button" className="button secondary" onClick={() => setRetry((value) => value + 1)}>Coba lagi</button></div> : loading ? <div className="affected-data-loading" role="status">Memuat baris terdampak…</div> : !result?.row_groups.length ? <div className="empty-state compact"><h3>{dataset.finding_count === 0 ? "Tidak ada temuan kualitas" : "Tidak ada baris yang cocok"}</h3><p>{dataset.finding_count === 0 ? "Tidak ditemukan masalah pada pemeriksaan yang dilakukan." : "Coba kata pencarian lain atau tampilkan semua temuan."}</p>{dataset.finding_count > 0 && <button type="button" className="button secondary" onClick={() => { setQuery(""); setSearch(""); setKind("all"); setPage(1); }}>Tampilkan semua temuan</button>}</div> : <>
      <div className="affected-data-scroll" role="region" aria-label="Tabel baris terdampak, geser untuk melihat semua kolom" tabIndex={0}>
        <table className="affected-data-table"><thead><tr>{sortHeader("_source_row", "Baris sumber")}{columns.map((column) => sortHeader(column, column.replaceAll("_", " ")))}</tr></thead><tbody>
          {result.row_groups.map((group) => {
            const selectedRow = selected?.row === group.row;
            const detailsId = `affected-row-${group.row}`;
            const rowId = `affected-row-toggle-${group.row}`;
            const visibleFindings = selectedRow && selected.column !== null ? group.findings.filter((finding) => finding.column === selected.column) : group.findings;
            const wholeRowFindings = group.findings.filter((finding) => finding.column === null);
            return <Fragment key={group.row}>
              <tr className={selectedRow ? "affected-row-selected" : ""} onClick={() => chooseRow(group.row)}>
                <th scope="row" className="affected-source-column"><button id={rowId} type="button" className="affected-row-toggle" aria-expanded={selectedRow} aria-controls={detailsId} onClick={(event) => { event.stopPropagation(); chooseRow(group.row); }}><strong>{group.row}</strong>{wholeRowFindings.length > 0 && <span className={wholeRowFindings.some((finding) => !isReview(finding)) ? "required" : "review"} aria-label="Temuan pada seluruh baris">!</span>}<ChevronDownIcon size={14} /></button></th>
                {columns.map((column) => {
                  const findings = group.findings.filter((finding) => finding.column === column);
                  const marked = findings.length > 0;
                  const markerKind = findings.some((finding) => !isReview(finding)) ? "required" : "review";
                  const original = group.source_record && Object.prototype.hasOwnProperty.call(group.source_record, column) ? group.source_record[column] : findings[0]?.original_value;
                  const tooltipId = `affected-tooltip-${group.row}-${columns.indexOf(column)}`;
                  const reason = Array.from(new Set(findings.map(hoverReason))).join(" · ");
                  return <td key={column} className={marked ? `affected-cell ${markerKind}` : ""}>
                    {marked ? <button type="button" className="affected-cell-value" aria-expanded={selectedRow && selected.column === column} aria-controls={detailsId} aria-describedby={tooltip?.id === tooltipId ? tooltipId : undefined} aria-label={`Baris ${group.row}, ${column}, ${displayValue(original)}. ${reason}`} onMouseEnter={(event) => showTooltip(event.currentTarget, tooltipId, reason)} onMouseLeave={() => setTooltip(null)} onFocus={(event) => showTooltip(event.currentTarget, tooltipId, reason)} onBlur={() => setTooltip(null)} onKeyDown={(event) => { if (event.key === "Escape") setTooltip(null); }} onClick={(event) => { event.stopPropagation(); setTooltip(null); chooseRow(group.row, column); }}><strong>{displayValue(original)}</strong>{findings.length > 1 && <small>{findings.length}</small>}</button> : <span className="affected-plain-value">{displayValue(original)}</span>}
                  </td>;
                })}
              </tr>
              {selectedRow && <tr className="affected-inline-row"><td colSpan={columns.length + 1}><section id={detailsId} className="affected-inline-detail" aria-label={`Rincian temuan baris ${group.row}`}>
                <header><div><h3>Baris sumber {group.row}{selected.column && ` · ${selected.column.replaceAll("_", " ")}`}</h3><span>{visibleFindings.length} temuan {selected.column ? "pada sel ini" : "pada baris ini"} · klik ulang baris atau sel untuk menutup</span></div><div>{selected.column !== null && <button type="button" onClick={() => setSelected({ row: group.row, column: null })}>Semua temuan baris</button>}<button type="button" onClick={() => onOpenSourceRow(group.row, rowId)}>Lihat baris lengkap</button></div></header>
                <div className="affected-detail-list">{visibleFindings.map((finding) => <article key={finding.id} className={`affected-finding ${isReview(finding) ? "review" : "required"}`}><div className="affected-finding-title"><div><strong>{formatIssueLabel(finding.issue_type)}</strong><span title={finding.column || undefined}>{finding.column?.replaceAll("_", " ") || "Seluruh baris"}</span></div><small>{isReview(finding) ? "Perlu konfirmasi" : "Ketidaksesuaian aturan"}</small></div><div className="affected-finding-body"><div className="affected-finding-values"><div><span>Nilai asli</span><strong>{displayValue(finding.original_value)}</strong></div>{finding.expected_value != null && <div><span>Rekomendasi</span><strong>{displayValue(finding.expected_value)}</strong></div>}</div><div className="affected-finding-explanation"><div><h4>Alasan penandaan</h4><p>{finding.evidence}</p></div><div><h4>Saran pemeriksaan</h4><p>{finding.recommendation}</p></div></div></div>{isReview(finding) && <p className="affected-confidence-note">Perlu konfirmasi sumber; nilai yang ditandai belum tentu salah.</p>}<details><summary>Metode dan keyakinan detektor</summary><p>{finding.detector} · {Math.round(finding.confidence * 100)}%. Skor ini bukan probabilitas bahwa nilai salah.</p></details></article>)}</div>
              </section></td></tr>}
            </Fragment>;
          })}
        </tbody></table>
      </div>
      {tooltip && <div id={tooltip.id} role="tooltip" className="affected-cell-tooltip" style={{ top: tooltip.top, left: tooltip.left }}>{tooltip.text}</div>}
      <footer className="pagination"><span>Baris terdampak {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, result.total_rows)} dari {result.total_rows.toLocaleString("id-ID")} · {result.total.toLocaleString("id-ID")} temuan</span><div><button type="button" className="icon-button" disabled={page === 1} aria-label="Halaman temuan sebelumnya" onClick={() => { setPage((value) => value - 1); setSelected(null); }}><ArrowLeftIcon size={16} /></button><span>{page} / {pageCount}</span><button type="button" className="icon-button" disabled={page >= pageCount} aria-label="Halaman temuan berikutnya" onClick={() => { setPage((value) => value + 1); setSelected(null); }}><ArrowRightIcon size={16} /></button></div></footer>
    </>}
    <details className="affected-coverage"><summary>Cakupan dan batas pemeriksaan</summary><p>Tabel menampilkan baris yang memiliki temuan. Penanda merah menunjukkan ketidaksesuaian aturan; amber menunjukkan potensi masalah yang perlu konfirmasi. Satu baris dapat memiliki kedua jenis temuan.</p>{executedChecks ? <p>Pemeriksaan deterministik/statistik: {executedChecks.length} dijalankan, {skippedChecks ?? 0} belum dijalankan karena prasyarat atau makna kolom belum sesuai. Dijalankan: {executedChecks.map((check) => check.toLowerCase().replaceAll("_", " ")).join(", ")}.</p> : <p>Assessment lama ini belum menyimpan log pemeriksaan yang dijalankan atau dilewati.</p>}<p>Pemeriksaan semantik: {dataset.source_metadata.semantic_recheck === "not_run" ? "tidak dijalankan ulang saat pengaturan jenis kolom diubah" : dataset.source_metadata.semantic_available === true ? "tersedia pada assessment ini" : "tidak tersedia atau tidak selesai pada assessment ini"}. Tidak adanya temuan bukan jaminan seluruh nilai benar.</p></details>
  </section>;
}
