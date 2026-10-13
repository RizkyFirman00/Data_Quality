import { DragEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, assessBackoffice, getConfig, listDatasets, previewDataset, uploadDataset } from "../api";
import { CheckIcon, RefreshIcon, ShieldCheckIcon, UploadCloudIcon } from "../icons";
import type { AssessmentPreview, DatasetSummary } from "../types";
import { displayOriginalValue as displayValue } from "../presentation";

const CHECK_LABELS: Record<string, string> = {
  FULL_ROW_DUPLICATE: "Duplikat baris penuh",
  MISSING_VALUE: "Nilai kosong dan placeholder",
  UPPERCASE: "Standar huruf uppercase",
  ADMINISTRATIVE_REFERENCE: "Referensi dan hierarki wilayah DKI",
  DATE_FORMAT: "Format tanggal dan periode data",
  NUMERIC_FORMAT: "Format numerik",
  COORDINATE: "Format dan rentang koordinat",
  CROSS_FIELD: "Konsistensi lintas kolom",
  CALCULATION: "Konsistensi perhitungan",
  STATISTICAL_ANOMALY: "Potensi anomali statistik",
  SEMANTIC_TYPO: "Potensi typo teks bebas melalui LLM",
};

const ROLE_LABELS: Record<string, string> = {
  text: "Teks",
  free_text: "Teks bebas",
  categorical: "Kategorikal",
  numeric: "Numerik",
  percentage: "Persentase",
  date: "Tanggal",
  identifier: "Identifier",
  latitude: "Lintang",
  longitude: "Bujur",
  administrative_city: "Kota/kabupaten",
  administrative_district: "Kecamatan",
  administrative_village: "Kelurahan",
};


export default function UploadDatasetPage() {
  const input = useRef<HTMLInputElement>(null);
  const previewRequest = useRef(0);
  const navigate = useNavigate();
  const [source, setSource] = useState<"file" | "backoffice">("file");
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [preview, setPreview] = useState<AssessmentPreview | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [configWarning, setConfigWarning] = useState("");
  const [maxUploadMb, setMaxUploadMb] = useState(25);
  const [backofficeEnabled, setBackofficeEnabled] = useState(false);
  const [history, setHistory] = useState<DatasetSummary[] | null>(null);
  const [parentId, setParentId] = useState("");

  useEffect(() => {
    getConfig()
      .then((config) => {
        setMaxUploadMb(config.max_upload_mb);
        setBackofficeEnabled(config.backoffice_enabled);
      })
      .catch(() => setConfigWarning("Konfigurasi layanan tidak dapat dimuat. Batas aman 25 MB digunakan untuk unggahan file."));
    listDatasets().then(setHistory).catch(() => setHistory([]));
  }, []);

  const choose = (candidate?: File) => {
    if (!candidate) return;
    previewRequest.current++;
    setPreviewing(false);
    setError(null);
    setPreview(null);
    if (!/\.(csv|xlsx|xls)$/i.test(candidate.name)) {
      setFile(null);
      setError(new ApiError("Gunakan file berformat CSV, XLSX, atau XLS."));
      return;
    }
    if (candidate.size > maxUploadMb * 1024 * 1024) {
      setFile(null);
      setError(new ApiError(`Ukuran file melebihi batas ${maxUploadMb} MB.`));
      return;
    }
    setFile(candidate);
  };

  const removeFile = () => {
    previewRequest.current++;
    setPreviewing(false);
    setFile(null);
    setPreview(null);
    setError(null);
    if (input.current) input.current.value = "";
  };

  const drop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    choose(event.dataTransfer.files[0]);
  };

  const loadPreview = async () => {
    if (!file || previewing) return;
    const sequence = ++previewRequest.current;
    setPreviewing(true);
    setError(null);
    try {
      const result = await previewDataset(file);
      if (sequence === previewRequest.current) setPreview(result);
    } catch (reason) {
      if (sequence === previewRequest.current) setError(reason instanceof ApiError ? reason : new ApiError("Preview dataset tidak dapat dibuat."));
    } finally {
      if (sequence === previewRequest.current) setPreviewing(false);
    }
  };

  const runAssessment = async () => {
    if (busy || (source === "file" && !file)) return;
    setBusy(true);
    setError(null);
    try {
      const dataset = source === "file"
        ? await uploadDataset(file!, parentId || undefined)
        : await assessBackoffice(parentId || undefined);
      navigate(`/datasets/${dataset.id}`);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason : new ApiError("Assessment tidak dapat diproses."));
    } finally {
      setBusy(false);
    }
  };

  const showParentSelect = backofficeEnabled || source === "backoffice";
  const disabled = busy || previewing || (source === "file" && !file);

  return (
    <main className="page narrow assessment-page">
      <Link className="back-link" to="/datasets">← Kembali ke dataset</Link>
      <div className="page-heading compact-heading">
        <div>
          <span className="eyebrow">Assessment baru</span>
          <h1>Periksa dataset</h1>
          <p>Pilih sumber data, lalu sistem akan membaca dan menampilkan temuannya.</p>
        </div>
      </div>
      <ol className="stepper" aria-label="Tahapan assessment">
        <li className={preview || busy ? "complete" : "active"}><span>{preview || busy ? <CheckIcon size={13} /> : "1"}</span>Pilih sumber</li>
        <li className={preview && !busy ? "active" : busy ? "complete" : ""}><span>{busy ? <CheckIcon size={13} /> : "2"}</span>Preview</li>
        <li className={busy ? "active" : ""}><span>3</span>Assessment</li>
        <li><span>4</span>Hasil</li>
      </ol>
      <section className="panel assessment-panel">
        {!preview && backofficeEnabled ? (
          <fieldset className="source-picker" disabled={busy || previewing}>
            <legend>Sumber data</legend>
            <button
              type="button"
              className={source === "file" ? "selected" : ""}
              aria-pressed={source === "file"}
              onClick={() => { setSource("file"); setError(null); }}
            >
              <i aria-hidden="true" />
              <span><strong>File dari perangkat</strong><small>CSV, XLSX, atau XLS</small></span>
            </button>
            <button
              type="button"
              className={source === "backoffice" ? "selected" : ""}
              aria-pressed={source === "backoffice"}
              onClick={() => { setSource("backoffice"); setError(null); }}
            >
              <i aria-hidden="true" />
              <span><strong>Backoffice</strong><small>Koneksi server yang tersedia</small></span>
            </button>
          </fieldset>
        ) : !preview ? (
          <div className="source-heading"><span>Sumber data</span><strong>File dari perangkat</strong></div>
        ) : null}
        {!preview && showParentSelect && (
          <div className="parent-select">
            <label htmlFor="parent-select">Parent assessment (opsional)</label>
            <select id="parent-select" value={parentId} onChange={(e) => setParentId(e.target.value)}>
              <option value="">Tidak ada assessment induk</option>
              {history?.map((ds) => (
                <option key={ds.id} value={ds.id}>
                  #{ds.id.slice(0, 8)} – {ds.original_filename}
                </option>
              ))}
            </select>
          </div>
        )}
        {busy ? (
          <div className="processing-state" role="status" aria-live="polite">
            <span className="spinner" aria-hidden="true" />
            <h2>Memeriksa dataset…</h2>
            <p>Sistem sedang membaca struktur, membuat profil, dan mencari potensi masalah. Waktu proses bergantung pada ukuran file.</p>
          </div>
        ) : preview ? (
          <div className="assessment-preview">
            <header className="preview-file-header">
              <div><span className="eyebrow">Preview dataset</span><h2>{preview.filename}</h2><p>{preview.worksheet_name ? `Worksheet ${preview.worksheet_name}` : preview.filename.split(".").pop()?.toUpperCase()} · belum disimpan sebagai assessment</p></div>
              <button className="button secondary" type="button" onClick={removeFile}>Pilih file lain</button>
            </header>
            <dl className="preview-metrics">
              <div><dt>Baris data</dt><dd>{preview.row_count.toLocaleString("id-ID")}</dd></div>
              <div><dt>Kolom</dt><dd>{preview.column_count.toLocaleString("id-ID")}</dd></div>
              <div><dt>Duplikat penuh</dt><dd>{preview.duplicate_row_count.toLocaleString("id-ID")}</dd></div>
            </dl>
            <section className="preview-section">
              <header><h3>Contoh data</h3><p>Maksimal 10 baris pertama. Nilai sumber belum diubah.</p></header>
              <div className="table-wrap preview-table"><table><thead><tr><th>Baris</th>{preview.columns.map((column) => <th key={column.position}>{column.display_name}</th>)}</tr></thead><tbody>{preview.rows.map((row) => <tr key={String(row._source_row)}><td className="row-number">{String(row._source_row)}</td>{preview.columns.map((column) => <td key={column.position} title={displayValue(row[column.display_name])}>{displayValue(row[column.display_name])}</td>)}</tr>)}</tbody></table></div>
            </section>
            <section className="preview-section">
              <header><h3>Pemahaman kolom</h3><p>Role sementara ditentukan secara deterministik sebelum assessment.</p></header>
              <div className="table-wrap preview-columns"><table><thead><tr><th>Kolom</th><th>Tipe terbaca</th><th>Role</th><th>Kosong</th><th>Unik</th></tr></thead><tbody>{preview.columns.map((column) => <tr key={column.position}><td className="column-name">{column.display_name}</td><td>{ROLE_LABELS[column.inferred_type] || column.inferred_type}</td><td>{ROLE_LABELS[column.candidate_role] || column.candidate_role}</td><td>{column.null_count + column.empty_count}</td><td>{column.unique_count}</td></tr>)}</tbody></table></div>
            </section>
            <section className="preview-section">
              <header><h3>Rencana pemeriksaan</h3><p>Dipilih dari profil awal; dapat berubah jika fungsi kolom diperjelas saat assessment.</p></header>
              <ul className="check-plan">{preview.checks.map((check) => <li key={check}><CheckIcon size={15} /><span>{CHECK_LABELS[check] || check}</span></li>)}</ul>
              {preview.checks.includes("SEMANTIC_TYPO") && <p className="preview-note">Analisis LLM dijalankan hanya untuk kandidat typo yang lolos filter. Jika 9Router tidak tersedia, pemeriksaan deterministik tetap dilanjutkan.</p>}
            </section>
          </div>
        ) : source === "file" ? (
          <>
            <input
              ref={input}
              type="file"
              accept=".csv,.xlsx,.xls"
              aria-label="Pilih file dataset CSV, XLSX, atau XLS"
              onChange={(event) => choose(event.target.files?.[0])}
              className="sr-only"
              id="dataset-file"
            />
            {file ? (
              <div className="selected-file">
                <span className="file-icon" aria-hidden="true">{file.name.split(".").pop()?.toUpperCase()}</span>
                <div>
                  <strong>{file.name}</strong>
                  <small>{(file.size / 1024).toLocaleString("id-ID", { maximumFractionDigits: 1 })} KB · siap diperiksa</small>
                </div>
                <button type="button" onClick={() => input.current?.click()}>Ganti</button>
                <button type="button" onClick={removeFile}>Hapus</button>
              </div>
            ) : (
              <div
                className={`drop-zone ${dragging ? "dragging" : ""}`}
                onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={drop}
              >
                <span className="upload-icon" aria-hidden="true"><UploadCloudIcon size={24} /></span>
                <h2>Tarik file ke sini</h2>
                <p>atau pilih file dari perangkat Anda</p>
                <button className="button secondary" type="button" onClick={() => input.current?.click()}>Pilih file</button>
              </div>
            )}
            <div className="upload-support">
              <span>Format: CSV, XLSX, XLS</span>
              <span>Maksimal {maxUploadMb} MB</span>
            </div>
          </>
        ) : (
          <div className="backoffice-source">
            <span aria-hidden="true"><RefreshIcon size={24} /></span>
            <h2>Ambil data dari Backoffice</h2>
            <p>Sistem menggunakan koneksi yang sudah dikonfigurasi di server. Kredensial tidak dikirim ke browser.</p>
          </div>
        )}
        {configWarning && <div className="inline-notice" role="status">{configWarning}</div>}
        {error && (
          <div className="feedback error" role="alert">
            <div>
              <strong>Assessment belum dapat diproses</strong>
              <p>{error.message}</p>
              {error.requestId && <code>ID: {error.requestId}</code>}
            </div>
          </div>
        )}
        <div className="preservation-note">
          <span aria-hidden="true"><ShieldCheckIcon size={15} /></span>
          <p><strong>Sumber tetap utuh.</strong> Sistem membuat salinan kerja terpisah untuk pemeriksaan.</p>
        </div>
        <div className="form-actions">
          <Link className="button ghost" to="/datasets">Batal</Link>
          {preview && <button className="button secondary" type="button" disabled={busy} onClick={() => setPreview(null)}>Kembali</button>}
          <button className="button primary" type="button" disabled={disabled} onClick={source === "file" && !preview ? loadPreview : runAssessment}>
            {busy ? "Memeriksa dataset…" : previewing ? "Membuat preview…" : preview ? "Jalankan assessment" : source === "backoffice" ? "Ambil dan periksa data" : "Lihat preview"}
          </button>
        </div>
      </section>
    </main>
  );
}
