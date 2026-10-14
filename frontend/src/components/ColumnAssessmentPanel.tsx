import { useEffect, useRef, useState } from "react";
import { getDataset, updateColumnRoles } from "../api";
import { readColumnAssessment } from "../presentation";
import type { DatasetDetail } from "../types";

const roleLabels: Record<string, string> = {
  auto: "Biarkan sistem menentukan", identifier: "Identifier / kode",
  numeric: "Ukuran numerik", percentage: "Persentase", categorical: "Kategori",
  free_text: "Teks bebas", date: "Tanggal", latitude: "Lintang", longitude: "Bujur",
};

export default function ColumnAssessmentPanel({ dataset, onUpdated }: {
  dataset: DatasetDetail; onUpdated: (dataset: DatasetDetail) => void;
}) {
  const columns = readColumnAssessment(dataset.source_metadata);
  const pending = columns?.filter((column) => column.status !== "ready") || [];
  const editable = columns?.filter((column) => column.status === "needs_role" || column.source === "user") || [];
  const revision = typeof dataset.source_metadata.role_revision === "number" ? dataset.source_metadata.role_revision : 0;
  const [roles, setRoles] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const details = useRef<HTMLDetailsElement>(null);
  const requestSequence = useRef(0);
  useEffect(() => () => { requestSequence.current++; }, [dataset.id]);
  useEffect(() => {
    setRoles(Object.fromEntries(editable.map((column) => [column.column, column.source === "user" ? column.effective_role : "auto"])));
    setError("");
  }, [dataset.id, revision]);

  const save = async (legacy = false) => {
    if (busy) return;
    const sequence = ++requestSequence.current;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await updateColumnRoles(dataset.id, legacy ? {} : roles, revision);
      if (sequence !== requestSequence.current) return;
      onUpdated(result);
      if (details.current) { details.current.open = false; details.current.querySelector<HTMLElement>("summary")?.focus(); }
      setMessage("Cakupan dan hasil pemeriksaan sudah diperbarui. File sumber tidak berubah.");
    } catch (reason) {
      if (sequence === requestSequence.current) setError(reason instanceof Error ? reason.message : "Pemeriksaan ulang gagal. Coba lagi; hasil sebelumnya tetap tersedia.");
    } finally { if (sequence === requestSequence.current) setBusy(false); }
  };

  const reload = async () => {
    if (busy) return;
    const sequence = ++requestSequence.current;
    setBusy(true); setError("");
    try {
      const result = await getDataset(dataset.id);
      if (sequence !== requestSequence.current) return;
      onUpdated(result);
      setMessage("Hasil terbaru dimuat. Periksa jenis kolom sebelum menyimpan lagi.");
    } catch (reason) {
      if (sequence === requestSequence.current) setError(reason instanceof Error ? reason.message : "Hasil terbaru tidak dapat dimuat. Coba lagi.");
    } finally { if (sequence === requestSequence.current) setBusy(false); }
  };

  return <section className="column-assessment" aria-label="Cakupan pemeriksaan kolom" aria-busy={busy}>
    <div className={`column-assessment-note${pending.length || !columns ? " pending" : ""}`}>
      <div><strong>{!columns ? "Cakupan kolom belum tercatat" : pending.length ? `${pending.length} kolom belum diperiksa penuh` : "Jenis kolom sudah ditentukan"}</strong>
        <p>{!columns ? "Assessment lama belum membedakan kolom yang jelas dan ambigu. Periksa ulang untuk memperbarui cakupannya." : pending.length ? "Pemeriksaan dasar tetap berjalan. Pemeriksaan berdasarkan makna kolom ditunda sampai jenisnya jelas." : "Hasil berlaku untuk pemeriksaan yang dijalankan, bukan jaminan semua nilai benar."}</p>
      </div>
      {!columns && <button type="button" className="button secondary" disabled={busy} onClick={() => save(true)}>{busy ? "Memeriksa ulang…" : "Periksa ulang cakupan"}</button>}
    </div>
    {columns && (pending.length > 0 || editable.length > 0) && <details className="column-role-settings" ref={details}>
      <summary>Atur jenis kolom <span>(opsional)</span></summary>
      <form onSubmit={(event) => { event.preventDefault(); save(); }}>
        <p className="column-role-help">Atur hanya kolom yang kamu kenali. Identifier tidak diperiksa dengan IQR; panjang/pola identifier tidak ditebak. Pemeriksaan semantik LLM tidak dijalankan ulang di sini.</p>
        <fieldset disabled={busy}>
          {editable.map((column, index) => <div className="column-role-row" key={column.column}>
            <div><label htmlFor={`column-role-${index}`}>{column.column}</label><p>{column.reason || "Jenis ditentukan oleh pengguna."}</p></div>
            <select id={`column-role-${index}`} value={roles[column.column] || "auto"} onChange={(event) => setRoles((current) => ({ ...current, [column.column]: event.target.value }))}>
              {Object.entries(roleLabels).map(([role, label]) => <option key={role} value={role}>{label}</option>)}
            </select>
          </div>)}
          {pending.filter((column) => column.status === "needs_header").map((column) => <div className="column-role-row" key={column.column}><div><strong>{column.column}</strong><p>{column.reason}</p></div><span className="column-role-help">Perlu header sumber</span></div>)}
          {editable.length > 0 && <div className="column-role-actions"><button type="submit" className="button primary">{busy ? "Memeriksa ulang…" : "Simpan dan periksa ulang"}</button><button type="button" className="button secondary" onClick={() => { setRoles(Object.fromEntries(editable.map((column) => [column.column, column.source === "user" ? column.effective_role : "auto"]))); if (details.current) { details.current.open = false; details.current.querySelector<HTMLElement>("summary")?.focus(); } }}>Batal</button></div>}
        </fieldset>
      </form>
    </details>}
    {error && <div className="column-role-error" role="alert"><p>{error}</p><button type="button" className="button secondary" disabled={busy} onClick={reload}>Muat ulang hasil</button></div>}
    {(busy || message) && <p className="column-role-help" role="status">{busy ? "Memperbarui pemeriksaan. Hasil sebelumnya tetap ditampilkan." : message}</p>}
  </section>;
}
