import { DragEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, getConfig, uploadDataset } from "../api";

export default function UploadDatasetPage() {
  const input = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [maxUploadMb, setMaxUploadMb] = useState<number | null>(null);

  useEffect(() => {
    getConfig().then(({ max_upload_mb }) => setMaxUploadMb(max_upload_mb)).catch((reason) => setError(reason instanceof ApiError ? reason : new ApiError("Konfigurasi unggahan tidak dapat dimuat.")));
  }, []);

  useEffect(() => {
    if (file && maxUploadMb !== null && file.size > maxUploadMb * 1024 * 1024) {
      setFile(null);
      setError(new ApiError(`Ukuran file melebihi batas ${maxUploadMb} MB.`));
    }
  }, [file, maxUploadMb]);

  const choose = (candidate?: File) => {
    setError(null);
    if (!candidate) return;
    if (!/\.(csv|xlsx)$/i.test(candidate.name)) {
      setFile(null);
      setError(new ApiError("Pilih file berformat CSV atau XLSX."));
      return;
    }
    if (maxUploadMb !== null && candidate.size > maxUploadMb * 1024 * 1024) {
      setFile(null);
      setError(new ApiError(`Ukuran file melebihi batas ${maxUploadMb} MB.`));
      return;
    }
    setFile(candidate);
  };

  const drop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    choose(event.dataTransfer.files[0]);
  };

  const submit = async () => {
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    try {
      const dataset = await uploadDataset(file);
      navigate(`/datasets/${dataset.id}`);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason : new ApiError("Dataset gagal diunggah."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="page narrow">
      <Link className="back-link" to="/datasets">← Kembali ke dataset</Link>
      <div className="page-heading upload-heading">
        <div><span className="eyebrow">Unggahan baru</span><h1>Periksa dataset OPD</h1><p>File asli disimpan tanpa perubahan. Tahap ini hanya membaca dan membuat profil data.</p></div>
      </div>
      <section className="upload-panel">
        <div className="step-label"><span>01</span><div><strong>Pilih sumber data</strong><small>CSV atau XLSX · {maxUploadMb === null ? "memuat batas ukuran…" : `maksimal ${maxUploadMb} MB`}</small></div></div>
        <div
          className={`drop-zone ${dragging ? "dragging" : ""} ${file ? "selected" : ""}`}
          onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={drop}
        >
          <input ref={input} type="file" accept=".csv,.xlsx" aria-label="Pilih file dataset CSV atau XLSX" onChange={(event) => choose(event.target.files?.[0])} className="sr-only" id="dataset-file" />
          {file ? (
            <><span className="file-icon">{file.name.split(".").pop()?.toUpperCase()}</span><h2>{file.name}</h2><p>{(file.size / 1024).toLocaleString("id-ID", { maximumFractionDigits: 1 })} KB · siap diproses</p><button className="text-link" type="button" onClick={() => input.current?.click()}>Ganti file</button></>
          ) : (
            <><span className="upload-arrow" aria-hidden="true">↑</span><h2>Letakkan file di area ini</h2><p>atau pilih dari perangkat Anda</p><button className="button secondary" type="button" onClick={() => input.current?.click()}>Pilih file</button></>
          )}
        </div>
        {error && <div className="message error" role="alert"><strong>File belum dapat diproses</strong><p>{error.message}</p>{error.requestId && <code>ID: {error.requestId}</code>}</div>}
        <div className="preservation-note"><span aria-hidden="true">◇</span><p><strong>Sumber tetap utuh.</strong> Sistem membuat salinan kerja terpisah untuk preview dan profiling.</p></div>
        <div className="form-actions"><Link className="button ghost" to="/datasets">Batal</Link><button className="button primary" type="button" disabled={!file || busy} onClick={submit}>{busy ? "Membaca dataset…" : "Unggah dan buat profil"}</button></div>
      </section>
    </main>
  );
}
