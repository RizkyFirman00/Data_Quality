import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, listDatasets } from "../api";
import { ChevronRightIcon, PlusIcon, SearchIcon } from "../icons";
import type { DatasetSummary } from "../types";
import { datasetAssessmentLabel as statusLabel, datasetAssessmentTone } from "../presentation";

const date = (value: string) => new Intl.DateTimeFormat("id-ID", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
const statusKey = (item: DatasetSummary) => item.status === "COMPLETED" ? item.assessment_status || item.status : item.status;

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<DatasetSummary[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("ALL");
  const load = useCallback(() => {
    setError(null);
    listDatasets().then(setDatasets).catch((reason) => setError(reason instanceof ApiError ? reason : new ApiError("Riwayat dataset tidak dapat dimuat.")));
  }, []);
  useEffect(load, [load]);
  const visible = useMemo(() => (datasets || []).filter((item) => item.original_filename.toLowerCase().includes(search.toLowerCase()) && (status === "ALL" || statusKey(item) === status)), [datasets, search, status]);

  return <main className="page">
    <div className="page-heading"><div><span className="eyebrow">Dataset</span><h1>Riwayat assessment</h1><p>Cari, buka, dan periksa kembali hasil dataset OPD.</p></div><Link className="button primary" to="/datasets/new"><PlusIcon size={16} /> Assessment baru</Link></div>
    <section className="panel dataset-panel" aria-labelledby="dataset-title"><header className="panel-header dataset-toolbar"><div><h2 id="dataset-title">Semua dataset</h2><p>{datasets ? `${datasets.length.toLocaleString("id-ID")} assessment tersimpan` : "Memuat riwayat…"}</p></div><div className="filter-controls"><label className="search-field"><span className="sr-only">Cari dataset</span><SearchIcon size={16} /><input name="dataset-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Cari nama dataset" /></label><label><span className="sr-only">Filter status</span><select name="dataset-status" value={status} onChange={(event) => setStatus(event.target.value)}><option value="ALL">Semua status</option><option value="PASSED">Tanpa temuan prioritas tinggi</option><option value="NEEDS_CORRECTION">Perlu koreksi</option><option value="PROCESSING">Diproses</option><option value="FAILED">Gagal</option></select></label></div></header>
      {error ? <div className="feedback error inset" role="alert"><div><strong>Riwayat tidak dapat dimuat</strong><p>{error.message}</p>{error.requestId && <code>ID: {error.requestId}</code>}</div><button className="button secondary" onClick={load}>Coba lagi</button></div> : datasets === null ? <div className="table-skeleton" aria-label="Memuat riwayat"><i /><i /><i /><i /></div> : datasets.length === 0 ? <div className="empty-state"><span aria-hidden="true"><PlusIcon size={20} /></span><h3>Belum ada dataset</h3><p>Mulai dengan CSV, XLSX, atau XLS.</p><Link className="button primary" to="/datasets/new">Mulai assessment</Link></div> : visible.length === 0 ? <div className="empty-state compact"><span aria-hidden="true"><SearchIcon size={20} /></span><h3>Dataset tidak ditemukan</h3><p>Ubah kata pencarian atau filter status.</p><button className="button secondary" onClick={() => { setSearch(""); setStatus("ALL"); }}>Hapus filter</button></div> : <div className="dataset-table" role="table" aria-label="Riwayat assessment"><div className="dataset-table-head" role="row"><span role="columnheader">Dataset</span><span role="columnheader">Format</span><span role="columnheader">Dimensi</span><span role="columnheader">Temuan</span><span role="columnheader">Diunggah</span><span role="columnheader">Status</span><span /></div>{visible.map((item) => <Link className="dataset-table-row" role="row" to={`/datasets/${item.id}`} key={item.id}><span role="cell" className="dataset-identity"><strong>{item.original_filename}</strong><small>{item.source_type === "backoffice_api" ? "Backoffice" : "Unggahan file"}</small></span><span role="cell"><b className="file-chip">{item.file_type.toUpperCase()}</b></span><span role="cell" data-label="Dimensi">{item.row_count.toLocaleString("id-ID")} × {item.column_count}</span><span role="cell" data-label="Temuan">{item.finding_count.toLocaleString("id-ID")}</span><time role="cell" data-label="Diunggah">{date(item.created_at)}</time><span role="cell"><b className={`status-chip ${datasetAssessmentTone(item)}`}>{statusLabel(item)}</b></span><ChevronRightIcon className="row-chevron" size={18} /></Link>)}</div>}
    </section>
  </main>;
}
