import { Fragment, useCallback, useDeferredValue, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, getComparison, getDataset, getPreview, listFindings, reportUrl } from "../api";
import { ArrowLeftIcon, ArrowRightIcon, CheckIcon, ChevronDownIcon, SearchIcon, ShieldCheckIcon } from "../icons";
import { formatIssueLabel, type DatasetDetail, type FindingPage, type PreviewPage, type PreviewRow } from "../types";

const value = (item: unknown) => item === null ? "NULL" : item === "" ? '""' : typeof item === "string" && !item.trim() ? "␠".repeat(item.length) : typeof item === "object" ? JSON.stringify(item) : String(item);
const date = (item: string) => new Intl.DateTimeFormat("id-ID", { dateStyle: "medium", timeStyle: "short" }).format(new Date(item));
const typeLabel: Record<string, string> = { integer: "Bilangan bulat", decimal: "Desimal", text: "Teks", free_text: "Teks bebas", address: "Alamat", date: "Tanggal", boolean: "Boolean", unknown: "Belum diketahui", identifier: "Identifier", numeric: "Numerik", percentage: "Persentase", latitude: "Lintang", longitude: "Bujur", categorical: "Kategorikal", geographic: "Geografis", administrative_city: "Kota/Kabupaten administratif", administrative_district: "Kecamatan administratif", administrative_village: "Kelurahan administratif" };

export default function DatasetDetailPage() {
  const { datasetId = "" } = useParams();
  const [dataset, setDataset] = useState<DatasetDetail | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [tab, setTab] = useState<"preview" | "profiles" | "findings">("preview");
  const [findings, setFindings] = useState<FindingPage | null>(null);
  const [findingError, setFindingError] = useState<ApiError | null>(null);
  const [findingLoading, setFindingLoading] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [severity, setSeverity] = useState("");
  const [issueType, setIssueType] = useState("");
  const [page, setPage] = useState(1);
  const [comparison, setComparison] = useState<{ available: boolean; resolved: string[]; remaining: string[]; new: string[] } | null>(null);

  const loadDataset = useCallback(() => {
    setError(null);
    getDataset(datasetId).then(setDataset).catch((reason) => setError(reason instanceof ApiError ? reason : new ApiError("Dataset tidak dapat dimuat.")));
  }, [datasetId]);
  useEffect(loadDataset, [loadDataset]);
  const loadFindingPage = useCallback(() => {
    setFindingLoading(true); setFindingError(null);
    listFindings(datasetId, { page, pageSize: 50, search: deferredSearch || undefined, severity: severity || undefined, issueType: issueType || undefined })
      .then(setFindings)
      .catch((reason) => setFindingError(reason instanceof ApiError ? reason : new ApiError("Temuan tidak dapat dimuat.")))
      .finally(() => setFindingLoading(false));
  }, [datasetId, deferredSearch, issueType, page, severity]);
  useEffect(() => { if (tab === "findings" && dataset?.status === "COMPLETED") loadFindingPage(); }, [dataset?.status, loadFindingPage, tab]);

  const [previewPage, setPreviewPage] = useState(1);
  const [previewData, setPreviewData] = useState<PreviewPage | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const previewPageSize = 25;

  const loadPreviewPage = useCallback(() => {
    setPreviewLoading(true);
    getPreview(datasetId, previewPage, previewPageSize)
      .then(setPreviewData)
      .catch(() => setPreviewData({ items: [], total: 0, page: previewPage, page_size: previewPageSize }))
      .finally(() => setPreviewLoading(false));
  }, [datasetId, previewPage, previewPageSize]);

  useEffect(() => {
    if (tab === "preview" && dataset?.status === "COMPLETED") loadPreviewPage();
  }, [dataset?.status, loadPreviewPage, tab]);

  const previewTotal = previewData?.total || dataset?.preview.length || 0;
  const previewPageCount = Math.max(1, Math.ceil(previewTotal / previewPageSize));
  const changePreviewPage = (delta: number) => {
    const next = Math.max(1, Math.min(previewPage + delta, previewPageCount));
    setPreviewPage(next);
  };
  const displayedPreview = previewData?.items || (dataset?.preview || []) as PreviewRow[];
  const columns = dataset?.column_profiles.map((column) => column.display_name) || [];
  const pageCount = Math.max(1, Math.ceil((findings?.total || 0) / 50));
  const changeFilter = (change: () => void) => { change(); setPage(1); setExpanded(null); };
  if (error) return <main className="page"><Link className="back-link" to="/datasets">← Kembali ke dataset</Link><div className="feedback error standalone"><div><strong>Dataset tidak dapat dibuka</strong><p>{error.message}</p></div><button className="button secondary" onClick={loadDataset}>Coba lagi</button></div></main>;
  if (!dataset) return <main className="page"><div className="detail-skeleton" aria-label="Memuat dataset"><i /><i /><i /><i /></div></main>;
  if (dataset.status === "FAILED") return <main className="page"><Link className="back-link" to="/datasets">← Kembali ke dataset</Link><div className="feedback error standalone"><div><strong>Pemrosesan dataset gagal</strong><p>{dataset.failure_message}</p></div></div></main>;
  if (dataset.status === "PROCESSING") return <main className="page"><Link className="back-link" to="/datasets">← Kembali ke dataset</Link><div className="processing-state standalone" role="status"><span className="spinner" /><h2>Dataset sedang diperiksa…</h2><p>Muat ulang halaman beberapa saat lagi.</p></div></main>;
  return <main className="page detail-page">
    <Link className="back-link" to="/datasets">← Kembali ke dataset</Link>
    <div className="detail-heading"><div><span className="eyebrow">Hasil assessment</span><h1>{dataset.original_filename}</h1><p>{dataset.source_type === "backoffice_api" ? "Sumber Backoffice" : dataset.worksheet_name ? `Worksheet ${dataset.worksheet_name}` : "Unggahan file"} · {dataset.completed_at && date(dataset.completed_at)}</p></div><div className="detail-actions"><a className="button secondary" href={reportUrl(dataset.id, "xlsx")}>Laporan XLSX</a><a className="button secondary" href={reportUrl(dataset.id, "pdf")}>Laporan PDF</a><span className={`status-chip ${dataset.assessment_status === "PASSED" ? "success" : "warning"}`}>{dataset.assessment_status === "PASSED" ? "Lulus" : "Perlu koreksi"}</span></div></div>
    <section className="summary-strip detail-summary" aria-label="Ringkasan dataset"><div><span>Baris</span><strong>{dataset.row_count.toLocaleString("id-ID")}</strong></div><div><span>Kolom</span><strong>{dataset.column_count}</strong></div><div><span>Format</span><strong className="text-value">{dataset.file_type.toUpperCase()}</strong></div><div><span>Total temuan</span><strong>{dataset.finding_count.toLocaleString("id-ID")}</strong><small>{dataset.finding_summary.by_severity.HIGH || 0} severity tinggi</small></div></section>
    <section className="panel detail-panel"><div className="tabs" role="tablist" aria-label="Detail dataset"><button role="tab" aria-selected={tab === "preview"} onClick={() => setTab("preview")}>Preview data <span>{dataset.preview.length}</span></button><button role="tab" aria-selected={tab === "profiles"} onClick={() => setTab("profiles")}>Profil kolom <span>{dataset.column_profiles.length}</span></button><button role="tab" aria-selected={tab === "findings"} onClick={() => setTab("findings")}>Temuan kualitas <span>{dataset.finding_count}</span></button></div>
      {tab === "preview" ? <div className="findings-view" role="tabpanel"><div className="table-wrap data-preview"><table><thead><tr><th className="source-column">Baris</th>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{displayedPreview.map((row) => <tr key={String(row._source_row)}><td className="source-column">{String(row._source_row)}</td>{columns.map((column) => <td key={column} className={row[column] === null ? "null-value" : ""} title={value(row[column])}>{value(row[column])}</td>)}</tr>)}</tbody></table></div>{previewPageCount > 1 && <footer className="pagination"><span>Menampilkan {(previewPage - 1) * previewPageSize + 1}–{Math.min(previewPage * previewPageSize, previewTotal)} dari {previewTotal.toLocaleString("id-ID")} baris · diurutkan berdasarkan baris sumber</span><div><button className="icon-button" disabled={previewPage === 1} onClick={() => changePreviewPage(-1)} aria-label="Halaman sebelumnya"><ArrowLeftIcon size={16} /></button><span>Halaman {previewPage} dari {previewPageCount}</span><button className="icon-button" disabled={previewPage >= previewPageCount} onClick={() => changePreviewPage(1)} aria-label="Halaman berikutnya"><ArrowRightIcon size={16} /></button></div></footer>}</div> : tab === "profiles" ? <div className="profile-list" role="tabpanel">{dataset.column_profiles.map((column) => <article className="profile-row" key={column.position}><span className="column-number">{String(column.position + 1).padStart(2, "0")}</span><div className="column-identity"><h3>{column.display_name}</h3>{column.original_name === "" && <small>Header asli kosong</small>}<div><span>{typeLabel[column.inferred_type] || column.inferred_type}</span><span>{typeLabel[column.candidate_role] || column.candidate_role}</span></div></div><dl><div><dt>Null</dt><dd>{column.null_count}</dd></div><div><dt>Kosong</dt><dd>{column.empty_count}</dd></div><div><dt>Unik</dt><dd>{column.unique_count}</dd></div></dl><div className="samples"><span>Sampel nilai</span><p>{column.sample_values.length ? column.sample_values.map(value).join(" · ") : "Tidak ada nilai"}</p>{column.distribution && <><span>Distribusi teratas</span><p>{column.distribution.map((item) => `${value(item.value)} (${item.count})`).join(" · ")}</p></>}</div></article>)}</div> : <div className="findings-view" role="tabpanel">
        {findingError ? <div className="feedback error inset"><div><strong>Temuan tidak dapat dimuat</strong><p>{findingError.message}</p></div><button className="button secondary" onClick={loadFindingPage}>Coba lagi</button></div> : !findings && findingLoading ? <div className="table-skeleton"><i /><i /><i /><i /></div> : findings && findings.total === 0 ? <div className="empty-state compact"><span aria-hidden="true">{dataset.finding_count ? <SearchIcon size={20} /> : <CheckIcon size={20} />}</span><h3>{dataset.finding_count ? "Temuan tidak ditemukan" : "Tidak ada temuan kualitas"}</h3><p>{dataset.finding_count ? "Ubah pencarian atau filter yang digunakan." : "Pemeriksaan tidak menemukan masalah pada dataset ini."}</p>{dataset.finding_count > 0 && <button className="button secondary" onClick={() => { setSearch(""); setSeverity(""); setIssueType(""); setPage(1); }}>Hapus filter</button>}</div> : findings && <><div className={`table-wrap findings-table ${findingLoading ? "refreshing" : ""}`}><table><thead><tr><th>Baris</th><th>Kolom</th><th>Temuan</th><th>Nilai saat ini</th><th>Nilai rekomendasi</th><th><span className="sr-only">Detail</span></th></tr></thead><tbody>{findings.items.map((finding) => <Fragment key={finding.id}><tr><td data-label="Baris" className="row-number">{finding.row}</td><td data-label="Kolom" className="column-name">{finding.column || "—"}</td><td data-label="Temuan" className="finding-issue-cell"><strong className="finding-title">{formatIssueLabel(finding.issue_type)}</strong><span className={`severity-chip ${finding.severity.toLowerCase()}`}>{finding.severity === "HIGH" ? "Tinggi" : "Medium"}</span></td><td data-label="Nilai saat ini" className="finding-value">{finding.original_value == null ? <span className="muted-value">—</span> : <code>{value(finding.original_value)}</code>}</td><td data-label="Nilai rekomendasi" className="finding-value">{finding.expected_value == null ? <span className="muted-value">—</span> : <code>{value(finding.expected_value)}</code>}</td><td><button className="disclosure" aria-expanded={expanded === finding.id} aria-label={`${expanded === finding.id ? "Tutup" : "Buka"} detail temuan baris ${finding.row}`} onClick={() => setExpanded(expanded === finding.id ? null : finding.id)}><ChevronDownIcon size={16} /></button></td></tr>{expanded === finding.id && <tr className="finding-detail-row"><td colSpan={6}><div><section><span>Evidence</span><p>{finding.evidence}</p></section><section><span>Rekomendasi tindakan</span><p>{finding.recommendation}</p></section></div></td></tr>}</Fragment>)}</tbody></table></div><footer className="pagination"><span>Menampilkan {(findings.page - 1) * findings.page_size + 1}–{Math.min(findings.page * findings.page_size, findings.total)} dari {findings.total.toLocaleString("id-ID")} temuan · diurutkan berdasarkan baris</span><div><button className="icon-button" disabled={page === 1 || findingLoading} onClick={() => { setPage(page - 1); setExpanded(null); }} aria-label="Halaman sebelumnya"><ArrowLeftIcon size={16} /></button><span>Halaman {page} dari {pageCount}</span><button className="icon-button" disabled={page >= pageCount || findingLoading} onClick={() => { setPage(page + 1); setExpanded(null); }} aria-label="Halaman berikutnya"><ArrowRightIcon size={16} /></button></div></footer></>}
        {dataset.parent_dataset_id && <div className="comparison"><button className="button secondary" type="button" onClick={() => getComparison(dataset.id).then(setComparison)}>Bandingkan assessment</button>{comparison && <span>{comparison.resolved.length} terselesaikan · {comparison.remaining.length} tetap · {comparison.new.length} baru</span>}</div>}
      </div>}
    </section><p className="source-footnote"><span aria-hidden="true"><ShieldCheckIcon size={15} /></span>Temuan adalah evidence untuk diperiksa. Dataset sumber tidak diubah.</p>
  </main>;
}
