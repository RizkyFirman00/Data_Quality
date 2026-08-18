import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, listDatasets } from "../api";
import type { DatasetSummary } from "../types";

const date = (value: string) => new Intl.DateTimeFormat("id-ID", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<DatasetSummary[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    listDatasets().then(setDatasets).catch((reason) => setError(reason instanceof ApiError ? reason : new ApiError("Riwayat dataset tidak dapat dimuat.")));
  }, []);

  return (
    <main className="page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">Ruang kerja reviewer</span>
          <h1>Dataset</h1>
          <p>Unggah, periksa struktur, dan pahami karakteristik data OPD.</p>
        </div>
        <Link className="button primary" to="/datasets/new">Unggah dataset <span aria-hidden="true">↗</span></Link>
      </div>

      <section className="ledger" aria-labelledby="history-title">
        <div className="section-title">
          <div><span className="section-index">01</span><h2 id="history-title">Riwayat unggahan</h2></div>
          {datasets && <span>{datasets.length} dataset</span>}
        </div>
        {error && <div className="message error"><strong>Riwayat gagal dimuat</strong><p>{error.message}</p>{error.requestId && <code>ID: {error.requestId}</code>}</div>}
        {!error && datasets === null && <div className="loading"><span /> Membaca riwayat dataset…</div>}
        {datasets?.length === 0 && (
          <div className="empty-state">
            <span className="empty-glyph" aria-hidden="true">＋</span>
            <h3>Belum ada dataset</h3>
            <p>Mulai dengan CSV atau XLSX dari OPD. File sumber akan tetap utuh.</p>
            <Link className="text-link" to="/datasets/new">Unggah dataset pertama →</Link>
          </div>
        )}
        {datasets && datasets.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Dataset</th><th>Format</th><th>Dimensi</th><th>Diunggah</th><th>Status</th><th><span className="sr-only">Buka</span></th></tr></thead>
              <tbody>
                {datasets.map((item) => (
                  <tr key={item.id}>
                    <td><Link className="dataset-name" to={`/datasets/${item.id}`}>{item.original_filename}</Link><small>File upload</small></td>
                    <td><span className="file-type">{item.file_type.toUpperCase()}</span></td>
                    <td className="tabular">{item.row_count.toLocaleString("id-ID")} × {item.column_count}</td>
                    <td>{date(item.created_at)}</td>
                    <td><span className={`status ${item.status.toLowerCase()}`}>{item.status === "COMPLETED" ? "Selesai" : item.status === "FAILED" ? "Gagal" : "Diproses"}</span></td>
                    <td><Link className="row-action" aria-label={`Buka ${item.original_filename}`} to={`/datasets/${item.id}`}>→</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
