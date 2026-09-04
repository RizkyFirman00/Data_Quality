import { DragEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, assessBackoffice, getConfig, listDatasets, uploadDataset } from "../api";
import { CheckIcon, RefreshIcon, ShieldCheckIcon, UploadCloudIcon } from "../icons";
import type { DatasetSummary } from "../types";

export default function UploadDatasetPage() {
  const input = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const [source, setSource] = useState<"file" | "backoffice">("file");
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
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
    setError(null);
    if (!candidate) return;
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
    setFile(null);
    setError(null);
    if (input.current) input.current.value = "";
  };

  const drop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    choose(event.dataTransfer.files[0]);
  };

  const submit = async () => {
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
  const disabled = busy || (source === "file" && !file);

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
        <li className={!busy ? "active" : "complete"}><span>{busy ? <CheckIcon size={13} /> : "1"}</span>Pilih sumber</li>
        <li className={busy ? "active" : ""}><span>2</span>Periksa data</li>
        <li><span>3</span>Lihat hasil</li>
      </ol>
      <section className="panel assessment-panel">
        {backofficeEnabled ? (
          <fieldset className="source-picker" disabled={busy}>
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
        ) : (
          <div className="source-heading"><span>Sumber data</span><strong>File dari perangkat</strong></div>
        )}
        {showParentSelect && (
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
          <button className="button primary" type="button" disabled={disabled} onClick={submit}>
            {busy ? "Memeriksa dataset…" : source === "backoffice" ? "Ambil dan periksa data" : "Unggah dan periksa"}
          </button>
        </div>
      </section>
    </main>
  );
}
