import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, getDashboard, listDatasets } from "../api";
import { CheckIcon, ChevronRightIcon, PlusIcon } from "../icons";
import { formatIssueLabel, type Dashboard, type DatasetSummary } from "../types";

const date = (value: string) => new Intl.DateTimeFormat("id-ID", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
const assessmentLabel = (item: DatasetSummary) => item.status === "FAILED" ? "Gagal" : item.status === "PROCESSING" ? "Diproses" : item.assessment_status === "PASSED" ? "Lulus" : "Perlu koreksi";

export default function DashboardPage() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [error, setError] = useState<ApiError | null>(null);
  const load = useCallback(() => {
    setError(null);
    Promise.all([getDashboard(), listDatasets()])
      .then(([summary, history]) => { setDashboard(summary); setDatasets(history); })
      .catch((reason) => setError(reason instanceof ApiError ? reason : new ApiError("Ringkasan assessment tidak dapat dimuat.")));
  }, []);
  useEffect(load, [load]);

  return <main className="page">
    <div className="page-heading"><div><span className="eyebrow">Ringkasan</span><h1>Assessment data</h1><p>Status faktual seluruh dataset yang sudah diperiksa.</p></div></div>
    {error ? <div className="feedback error" role="alert"><div><strong>Ringkasan tidak dapat dimuat</strong><p>{error.message}</p></div><button className="button secondary" onClick={load}>Coba lagi</button></div> : !dashboard ? <div className="dashboard-skeleton" aria-label="Memuat ringkasan"><i /><i /><i /><i /></div> : <>
      <section className="summary-strip" aria-label="Ringkasan assessment">
        <div><span>Total assessment</span><strong>{dashboard.total_assessments.toLocaleString("id-ID")}</strong></div>
        <div><span>Lulus</span><strong>{dashboard.passed_assessments.toLocaleString("id-ID")}</strong></div>
        <div><span>Perlu koreksi</span><strong>{dashboard.needs_correction_assessments.toLocaleString("id-ID")}</strong></div>
        <div><span>Temuan terbuka</span><strong>{dashboard.open_findings.toLocaleString("id-ID")}</strong></div>
      </section>
      <div className="dashboard-grid">
        <section className="panel recent-panel" aria-labelledby="recent-title"><header className="panel-header"><div><h2 id="recent-title">Assessment terbaru</h2><p>Diurutkan berdasarkan waktu unggah.</p></div><Link to="/datasets">Lihat semua</Link></header>
          {datasets.length ? <div className="dataset-rows">{datasets.slice(0, 4).map((item) => <Link className="dataset-row" to={`/datasets/${item.id}`} key={item.id}><div><strong>{item.original_filename}</strong><span>{item.row_count.toLocaleString("id-ID")} baris · {item.finding_count.toLocaleString("id-ID")} temuan</span></div><time>{date(item.created_at)}</time><span className={`status-chip ${item.assessment_status === "PASSED" ? "success" : item.status === "FAILED" ? "danger" : "warning"}`}>{assessmentLabel(item)}</span><ChevronRightIcon className="row-chevron" size={18} /></Link>)}</div> : <div className="empty-state compact"><span aria-hidden="true"><PlusIcon size={20} /></span><h3>Belum ada assessment</h3><p>Unggah CSV atau XLSX untuk mulai memeriksa data.</p><Link className="button primary" to="/datasets/new">Mulai assessment</Link></div>}
        </section>
        <section className="panel latest-panel" aria-labelledby="latest-title">{dashboard.latest_assessment ? <><header className="panel-header"><div><h2 id="latest-title">Temuan assessment terakhir</h2><p>{dashboard.latest_assessment.original_filename}<br />{date(dashboard.latest_assessment.completed_at)}</p></div><Link to={`/datasets/${dashboard.latest_assessment.id}`}>Lihat assessment</Link></header><div className="issue-list">{Object.entries(dashboard.latest_assessment.issue_counts).sort((a, b) => b[1] - a[1]).map(([issue, count]) => <div key={issue}><span>{formatIssueLabel(issue)}</span><strong>{count}</strong></div>)}{dashboard.latest_assessment.finding_count === 0 && <div className="latest-clean"><span aria-hidden="true"><CheckIcon size={18} /></span><p>Tidak ada temuan pada assessment terakhir.</p></div>}</div><footer className="panel-footer">Total {dashboard.latest_assessment.finding_count.toLocaleString("id-ID")} temuan pada dataset ini.</footer></> : <div className="empty-state compact"><span aria-hidden="true"><PlusIcon size={20} /></span><h3>Belum ada hasil assessment</h3><p>Temuan dari assessment terakhir akan tampil di sini.</p><Link className="button primary" to="/datasets/new">Mulai assessment</Link></div>}</section>
      </div>
    </>}
  </main>;
}
