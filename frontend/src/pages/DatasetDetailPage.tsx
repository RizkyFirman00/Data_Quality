import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import FindingsDataTable from "../components/FindingsDataTable";
import ColumnAssessmentPanel from "../components/ColumnAssessmentPanel";
import { ApiError, getComparison, getDataset, getPreview, reportUrl } from "../api";
import { ArrowLeftIcon, ArrowRightIcon, ShieldCheckIcon } from "../icons";
import { type DatasetDetail, type PreviewPage, type PreviewRow } from "../types";
import { datasetAssessmentLabel, datasetAssessmentTone, displayOriginalValue as value } from "../presentation";

const date = (item: string) => new Intl.DateTimeFormat("id-ID", { dateStyle: "medium", timeStyle: "short" }).format(new Date(item));
const typeLabel: Record<string, string> = { integer: "Bilangan bulat", decimal: "Desimal", text: "Teks", free_text: "Teks bebas", address: "Alamat", date: "Tanggal", boolean: "Boolean", unknown: "Belum diketahui", identifier: "Identifier", numeric: "Numerik", percentage: "Persentase", latitude: "Lintang", longitude: "Bujur", categorical: "Kategorikal", geographic: "Geografis", administrative_city: "Kota/Kabupaten administratif", administrative_district: "Kecamatan administratif", administrative_village: "Kelurahan administratif" };
export default function DatasetDetailPage() {
  const { datasetId = "" } = useParams();
  const [dataset, setDataset] = useState<DatasetDetail | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [tab, setTab] = useState<"preview" | "profiles" | "findings">("findings");
  const [comparison, setComparison] = useState<{ resolved: string[]; remaining: string[]; new: string[] } | null>(null);
  const [comparisonError, setComparisonError] = useState<string | null>(null);
  const datasetRequest = useRef(0);
  const previewRequest = useRef(0);
  const loadDataset = useCallback(() => {
    const sequence = ++datasetRequest.current;
    setDataset(null);
    setError(null);
    getDataset(datasetId).then((result) => { if (sequence === datasetRequest.current) setDataset(result); }).catch((reason) => { if (sequence === datasetRequest.current) setError(reason instanceof ApiError ? reason : new ApiError("Dataset tidak dapat dimuat.")); });
  }, [datasetId]);
  useEffect(() => { loadDataset(); return () => { datasetRequest.current++; }; }, [loadDataset]);
  const [previewPage, setPreviewPage] = useState(1);
  const [previewData, setPreviewData] = useState<PreviewPage | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [focusedSourceRow, setFocusedSourceRow] = useState<number | null>(null);
  const [returnFindingId, setReturnFindingId] = useState<string | null>(null);
  const previewPageSize = 25;
  useEffect(() => {
    setPreviewPage(1); setPreviewData(null); setPreviewError(null); setFocusedSourceRow(null);
    setReturnFindingId(null); setComparison(null); setComparisonError(null); setTab("findings");
    return () => { previewRequest.current++; };
  }, [datasetId]);

  const loadPreviewPage = useCallback(() => {
    const sequence = ++previewRequest.current;
    setPreviewLoading(true);
    setPreviewError(null);
    getPreview(datasetId, previewPage, previewPageSize, focusedSourceRow ?? undefined)
      .then((result) => { if (sequence === previewRequest.current) { setPreviewData(result); setPreviewPage(result.page); } })
      .catch((reason) => { if (sequence === previewRequest.current) setPreviewError(reason instanceof Error ? reason.message : "Preview tidak dapat dimuat."); })
      .finally(() => { if (sequence === previewRequest.current) setPreviewLoading(false); });
  }, [datasetId, previewPage, previewPageSize, focusedSourceRow]);

  useEffect(() => {
    if (tab === "preview" && dataset?.status === "COMPLETED") loadPreviewPage();
  }, [dataset?.status, loadPreviewPage, tab]);

  useEffect(() => {
    if (tab !== "preview" || previewLoading || focusedSourceRow == null) return;
    const rows = Array.from(document.querySelectorAll<HTMLTableRowElement>(".data-preview tbody tr"));
    const row = rows.find((item) => item.cells[0]?.textContent === String(focusedSourceRow));
    if (!row) return;
    row.classList.add("source-row-highlight");
    row.tabIndex = -1;
    row.scrollIntoView({ block: "center", inline: "start" });
    row.focus({ preventScroll: true });
    return () => row.classList.remove("source-row-highlight");
  }, [tab, previewData, previewLoading, focusedSourceRow]);

  const openSourceRow = (row: number, findingId: string) => {
    setReturnFindingId(findingId);
    setFocusedSourceRow(row);
    setTab("preview");
  };
  const returnToFinding = () => {
    setTab("findings");
    requestAnimationFrame(() => {
      const target = returnFindingId && document.getElementById(returnFindingId);
      if (target) { target.scrollIntoView({ block: "center" }); target.focus({ preventScroll: true }); }
    });
  };

  const previewTotal = previewData?.total || dataset?.preview.length || 0;
  const previewPageCount = Math.max(1, Math.ceil(previewTotal / previewPageSize));
  const changePreviewPage = (delta: number) => {
    setFocusedSourceRow(null);
    const next = Math.max(1, Math.min(previewPage + delta, previewPageCount));
    setPreviewPage(next);
  };
  const displayedPreview = previewData?.items || (dataset?.preview || []) as PreviewRow[];
  const columns = dataset?.column_profiles.map((column) => column.display_name) || [];
  if (error) return <main className="page"><Link className="back-link" to="/datasets">← Kembali ke dataset</Link><div className="feedback error standalone"><div><strong>Dataset tidak dapat dibuka</strong><p>{error.message}</p></div><button className="button secondary" onClick={loadDataset}>Coba lagi</button></div></main>;
  if (!dataset) return <main className="page"><div className="detail-skeleton" aria-label="Memuat dataset"><i /><i /><i /><i /></div></main>;
  if (dataset.status === "FAILED") return <main className="page"><Link className="back-link" to="/datasets">← Kembali ke dataset</Link><div className="feedback error standalone"><div><strong>Pemrosesan dataset gagal</strong><p>{dataset.failure_message}</p></div></div></main>;
  if (dataset.status === "PROCESSING") return <main className="page"><Link className="back-link" to="/datasets">← Kembali ke dataset</Link><div className="processing-state standalone" role="status"><span className="spinner" /><h2>Dataset sedang diperiksa…</h2><p>Muat ulang halaman beberapa saat lagi.</p></div></main>;
  return <main className="page detail-page">
    <Link className="back-link" to="/datasets">← Kembali ke dataset</Link>
    <section className="dataset-dossier" aria-label="Identitas dan ringkasan dataset">
    <div className="detail-heading"><div className="dataset-identity"><div className="dataset-heading-meta"><span className="eyebrow">Hasil assessment</span><span className={`status-chip ${datasetAssessmentTone(dataset)}`}>{datasetAssessmentLabel(dataset)}</span></div><h1>{dataset.original_filename}</h1><p>{dataset.source_type === "backoffice_api" ? "Sumber Backoffice" : dataset.worksheet_name ? `Worksheet ${dataset.worksheet_name}` : "Unggahan file"} · {dataset.completed_at && date(dataset.completed_at)}</p></div><div className="detail-actions" aria-label="Unduh laporan"><span>Laporan</span><a className="button secondary" href={reportUrl(dataset.id, "xlsx")}>XLSX</a><a className="button secondary" href={reportUrl(dataset.id, "pdf")}>PDF</a></div></div>
    <section className="summary-strip detail-summary" aria-label="Ringkasan dataset"><div><span>Baris</span><strong>{dataset.row_count.toLocaleString("id-ID")}</strong></div><div><span>Kolom</span><strong>{dataset.column_count}</strong></div><div><span>Format</span><strong className="text-value">{dataset.file_type.toUpperCase()}</strong></div><div><span>Total temuan</span><strong>{dataset.finding_count.toLocaleString("id-ID")}</strong><small>{dataset.finding_summary.by_severity.HIGH || 0} severity tinggi</small></div></section>
    </section>
    <ColumnAssessmentPanel dataset={dataset} onUpdated={(updated) => { setDataset(updated); setComparison(null); }} />
    {tab === "preview" && Boolean(returnFindingId || focusedSourceRow != null || previewLoading || previewError) && <div className="finding-preview-navigation">{returnFindingId && <button className="finding-evidence-link" type="button" onClick={returnToFinding}>Kembali ke temuan</button>}{focusedSourceRow != null && <span>Baris sumber {focusedSourceRow} ditandai pada Preview.</span>}{previewLoading && <span role="status">Memuat baris dataset…</span>}{previewError && <div role="alert"><p>{previewError}</p><button type="button" className="finding-evidence-link" onClick={loadPreviewPage}>Coba lagi</button></div>}</div>}
    <section className="panel detail-panel"><div className="tabs" role="tablist" aria-label="Detail dataset"><button role="tab" aria-selected={tab === "preview"} onClick={() => setTab("preview")}>Preview data <span>{dataset.row_count.toLocaleString("id-ID")}</span></button><button role="tab" aria-selected={tab === "profiles"} onClick={() => setTab("profiles")}>Profil kolom <span>{dataset.column_profiles.length}</span></button><button role="tab" aria-selected={tab === "findings"} onClick={() => setTab("findings")}>Temuan kualitas <span>{dataset.finding_count}</span></button></div>
      {tab === "preview" ? <div className="findings-view" role="tabpanel"><div className="table-wrap data-preview"><table><thead><tr><th className="source-column">Baris</th>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{displayedPreview.map((row) => <tr key={String(row._source_row)}><td className="source-column">{String(row._source_row)}</td>{columns.map((column) => <td key={column} className={row[column] === null ? "null-value" : ""} title={value(row[column])}>{value(row[column])}</td>)}</tr>)}</tbody></table></div>{previewPageCount > 1 && <footer className="pagination"><span>Menampilkan {(previewPage - 1) * previewPageSize + 1}–{Math.min(previewPage * previewPageSize, previewTotal)} dari {previewTotal.toLocaleString("id-ID")} baris · diurutkan berdasarkan baris sumber</span><div><button className="icon-button" disabled={previewPage === 1} onClick={() => changePreviewPage(-1)} aria-label="Halaman sebelumnya"><ArrowLeftIcon size={16} /></button><span>Halaman {previewPage} dari {previewPageCount}</span><button className="icon-button" disabled={previewPage >= previewPageCount} onClick={() => changePreviewPage(1)} aria-label="Halaman berikutnya"><ArrowRightIcon size={16} /></button></div></footer>}</div> : tab === "profiles" ? <div className="profile-list" role="tabpanel">{dataset.column_profiles.map((column) => <article className="profile-row" key={column.position}><span className="column-number">{String(column.position + 1).padStart(2, "0")}</span><div className="column-identity"><h3>{column.display_name}</h3>{column.original_name === "" && <small>Header asli kosong</small>}<div><span>{typeLabel[column.inferred_type] || column.inferred_type}</span><span>{typeLabel[column.candidate_role] || column.candidate_role}</span></div></div><dl><div><dt>Null</dt><dd>{column.null_count}</dd></div><div><dt>Kosong</dt><dd>{column.empty_count}</dd></div><div><dt>Unik</dt><dd>{column.unique_count}</dd></div></dl><div className="samples"><span>Sampel nilai</span><p>{column.sample_values.length ? column.sample_values.map(value).join(" · ") : "Tidak ada nilai"}</p>{column.distribution && <><span>Distribusi teratas</span><p>{column.distribution.map((item) => `${value(item.value)} (${item.count})`).join(" · ")}</p></>}</div></article>)}</div> : null}
      <div hidden={tab !== "findings"}><FindingsDataTable key={`${dataset.id}:${dataset.source_metadata.role_revision ?? 0}`} dataset={dataset} onOpenSourceRow={openSourceRow} /></div>
      {tab === "findings" && dataset.parent_dataset_id && <div className="comparison"><button type="button" className="button secondary" onClick={() => { setComparisonError(null); getComparison(dataset.id).then(setComparison).catch((reason) => setComparisonError(reason instanceof Error ? reason.message : "Perbandingan tidak dapat dimuat.")); }}>Bandingkan assessment</button>{comparison && <span>{comparison.resolved.length} terselesaikan · {comparison.remaining.length} tetap · {comparison.new.length} baru</span>}{comparisonError && <span role="alert">{comparisonError}</span>}</div>}
    </section><p className="source-footnote"><span aria-hidden="true"><ShieldCheckIcon size={15} /></span>Temuan adalah bukti untuk diperiksa. Dataset sumber tidak diubah.</p>
  </main>;
}
