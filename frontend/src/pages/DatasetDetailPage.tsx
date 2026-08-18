import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, getDataset } from "../api";
import type { DatasetDetail, FindingIssueType } from "../types";

const value = (item: unknown) => item === null ? "NULL" : item === "" ? '""' : typeof item === "string" && !item.trim() ? "␠".repeat(item.length) : typeof item === "object" ? JSON.stringify(item) : String(item);
const date = (item: string) => new Intl.DateTimeFormat("id-ID", { dateStyle: "medium", timeStyle: "short" }).format(new Date(item));
const label: Record<string, string> = { integer: "Bilangan bulat", decimal: "Desimal", text: "Teks", date: "Tanggal", boolean: "Boolean", unknown: "Belum diketahui", identifier: "Identifier", numeric: "Numerik", categorical: "Kategorikal", geographic: "Geografis", administrative_city: "Kota/Kabupaten administratif", administrative_district: "Kecamatan administratif", administrative_village: "Kelurahan administratif" };
const issueLabel: Record<FindingIssueType, string> = { DUPLICATE: "Duplikat penuh", MISSING_VALUE: "Nilai kosong", INVALID_PLACEHOLDER: "Placeholder tidak valid", INVALID_CASE: "Bukan uppercase", INVALID_REFERENCE: "Referensi tidak valid", INVALID_HIERARCHY: "Hierarki tidak valid" };

export default function DatasetDetailPage() {
  const { datasetId = "" } = useParams();
  const [dataset, setDataset] = useState<DatasetDetail | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [tab, setTab] = useState<"preview" | "profiles" | "findings">("preview");

  useEffect(() => { getDataset(datasetId).then(setDataset).catch((reason) => setError(reason instanceof ApiError ? reason : new ApiError("Dataset tidak dapat dimuat."))); }, [datasetId]);

  if (error) return <main className="page"><Link className="back-link" to="/datasets">← Kembali ke dataset</Link><div className="message error standalone"><strong>Dataset tidak dapat dibuka</strong><p>{error.message}</p></div></main>;
  if (!dataset) return <main className="page"><div className="loading"><span /> Membaca struktur dataset…</div></main>;
  if (dataset.status === "FAILED") return <main className="page"><Link className="back-link" to="/datasets">← Kembali ke dataset</Link><div className="message error standalone"><strong>Pemrosesan dataset gagal</strong><p>{dataset.failure_message}</p></div></main>;
  if (dataset.status === "PROCESSING") return <main className="page"><Link className="back-link" to="/datasets">← Kembali ke dataset</Link><div className="loading"><span /> Dataset sedang diproses…</div></main>;

  const columns = dataset.column_profiles.map((column) => column.display_name);
  return (
    <main className="page detail-page">
      <Link className="back-link" to="/datasets">← Kembali ke dataset</Link>
      <div className="detail-title"><div><span className="eyebrow">Profil &amp; kualitas data</span><h1>{dataset.original_filename}</h1><p>{dataset.worksheet_name ? `Worksheet: ${dataset.worksheet_name}` : "Sumber: unggahan file"}</p><p>Diunggah: {date(dataset.created_at)} · Selesai: {date(dataset.completed_at!)}</p></div><span className="status completed">Selesai diperiksa</span></div>
      <section className="facts" aria-label="Ringkasan dataset">
        <div><span>Baris</span><strong>{dataset.row_count.toLocaleString("id-ID")}</strong></div>
        <div><span>Kolom</span><strong>{dataset.column_count}</strong></div>
        <div><span>Format</span><strong className="small-value">{dataset.file_type.toUpperCase()}</strong></div>
        <div><span>Total temuan</span><strong>{dataset.finding_count}</strong><small>{dataset.finding_summary.by_severity.HIGH || 0} severity tinggi</small></div>
      </section>
      <section className="ledger detail-ledger">
        <div className="tabs" role="tablist" aria-label="Detail dataset">
          <button role="tab" aria-selected={tab === "preview"} onClick={() => setTab("preview")}>Preview data <span>{dataset.preview.length}</span></button>
          <button role="tab" aria-selected={tab === "profiles"} onClick={() => setTab("profiles")}>Profil kolom <span>{dataset.column_profiles.length}</span></button>
          <button role="tab" aria-selected={tab === "findings"} onClick={() => setTab("findings")}>Temuan kualitas <span>{dataset.finding_count}</span></button>
        </div>
        {tab === "preview" ? (
          <div className="table-wrap data-preview" role="tabpanel">
            <table><thead><tr><th className="source-column">BARIS</th>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{dataset.preview.map((row) => <tr key={String(row._source_row)}><td className="source-column">{String(row._source_row).padStart(3, "0")}</td>{columns.map((column) => <td key={column} className={row[column] === null ? "null-value" : ""}>{value(row[column])}</td>)}</tr>)}</tbody></table>
          </div>
        ) : tab === "profiles" ? (
          <div className="profile-list" role="tabpanel">
            {dataset.column_profiles.map((column) => (
              <article className="profile-row" key={column.position}>
                <span className="column-number">{String(column.position + 1).padStart(2, "0")}</span>
                <div className="column-identity"><h3>{column.display_name}</h3>{column.original_name === "" && <small>Header asli kosong</small>}<div><span>{label[column.inferred_type] || column.inferred_type}</span><span>{label[column.candidate_role] || column.candidate_role} · terdeteksi</span></div></div>
                <dl><div><dt>Null</dt><dd>{column.null_count}</dd></div><div><dt>Kosong</dt><dd>{column.empty_count}</dd></div><div><dt>Unik</dt><dd>{column.unique_count}</dd></div></dl>
                <div className="samples"><span>Sampel nilai</span><p>{column.sample_values.length ? column.sample_values.map(value).join(" · ") : "Tidak ada nilai"}</p>{column.distribution && <><span>Distribusi teratas</span><p>{column.distribution.map((item) => `${value(item.value)} (${item.count})`).join(" · ")}</p></>}</div>
              </article>
            ))}
          </div>
        ) : (
          <div className="findings-panel" role="tabpanel">
            <div className="finding-summary" aria-label="Ringkasan temuan kualitas">
              {Object.entries(issueLabel).map(([issue, text]) => <div key={issue}><span>{text}</span><strong>{dataset.finding_summary.by_issue_type[issue as FindingIssueType] || 0}</strong></div>)}
              <div className="severity-total high"><span>Severity tinggi</span><strong>{dataset.finding_summary.by_severity.HIGH || 0}</strong></div>
              <div className="severity-total medium"><span>Severity medium</span><strong>{dataset.finding_summary.by_severity.MEDIUM || 0}</strong></div>
            </div>
            {dataset.findings.length ? (
              <div className="table-wrap findings-table">
                <table>
                  <thead><tr><th>Severity</th><th>Baris</th><th>Kolom</th><th>Isu</th><th>Nilai saat ini</th><th>Evidence</th><th>Rekomendasi</th></tr></thead>
                  <tbody>{dataset.findings.map((finding) => <tr key={finding.id}>
                    <td><span className={`severity ${finding.severity.toLowerCase()}`}>{finding.severity === "HIGH" ? "Tinggi" : "Medium"}</span></td>
                    <td className="tabular">{finding.row}</td>
                    <td>{finding.column || "Seluruh baris"}</td>
                    <td><strong>{issueLabel[finding.issue_type]}</strong></td>
                    <td className="finding-value">{value(finding.original_value)}</td>
                    <td>{finding.evidence}</td>
                    <td>{finding.recommendation}</td>
                  </tr>)}</tbody>
                </table>
              </div>
            ) : <div className="empty-state compact"><span className="empty-glyph" aria-hidden="true">✓</span><h3>Tidak ada temuan kualitas</h3><p>Pemeriksaan struktural dan referensi administratif tidak menemukan masalah.</p></div>}
          </div>
        )}
      </section>
      <p className="phase-boundary"><strong>Catatan reviewer:</strong> temuan adalah evidence dan rekomendasi untuk diverifikasi. Dataset sumber tidak diubah.</p>
    </main>
  );
}
