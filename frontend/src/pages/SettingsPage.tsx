import { useCallback, useEffect, useState } from "react";
import { ApiError, getSystemSettings } from "../api";
import type { SystemSettings } from "../types";
import type { LocalUser } from "../types";
import AccountManagement from "../components/AccountManagement";

const number = (value: number) => value.toLocaleString("id-ID");
export default function SettingsPage({ user }: { user: LocalUser }) {
  const [data, setData] = useState<SystemSettings | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const load = useCallback(() => { setError(null); getSystemSettings().then(setData).catch((reason) => setError(reason instanceof ApiError ? reason : new ApiError("Pengaturan tidak dapat dimuat."))); }, []);
  useEffect(load, [load]);
  return <main className="page narrow"><div className="page-heading"><div><span className="eyebrow">Pengaturan</span><h1>{user.is_admin ? "Akun dan sistem" : "Kapabilitas sistem"}</h1><p>{user.is_admin ? "Buat akun pengguna dan lihat konfigurasi assessment." : "Konfigurasi aktif sistem, tanpa menampilkan kredensial layanan."}</p></div></div>
    {user.is_admin && <AccountManagement currentUserId={user.id} />}
    {error ? <div className="feedback error"><div><strong>Pengaturan tidak dapat dimuat</strong><p>{error.message}</p></div><button className="button secondary" onClick={load}>Coba lagi</button></div> : !data ? <div className="detail-skeleton"><i /><i /><i /></div> : <div className="settings-stack">
      <section className="panel settings-section"><header className="panel-header"><div><h2>Batas assessment</h2><p>Proteksi kapasitas pada file masuk.</p></div></header><dl><div><dt>Ukuran unggahan</dt><dd>{data.limits.upload_mb} MB</dd></div><div><dt>Maksimal baris</dt><dd>{number(data.limits.rows)}</dd></div><div><dt>Maksimal kolom</dt><dd>{number(data.limits.columns)}</dd></div><div><dt>Maksimal sel</dt><dd>{number(data.limits.cells)}</dd></div><div><dt>Maksimal temuan</dt><dd>{number(data.limits.findings)}</dd></div></dl></section>
      <section className="panel settings-section"><header className="panel-header"><div><h2>Integrasi dan format</h2><p>Status konfigurasi tanpa menampilkan endpoint atau token.</p></div></header><dl><div><dt>Login</dt><dd>Akun lokal · session {data.authentication.session_hours} jam</dd></div><div><dt>Semantic LLM</dt><dd><span className={`status-chip ${data.semantic.enabled ? "success" : "neutral"}`}>{data.semantic.enabled ? "Aktif" : "Tidak aktif"}</span></dd></div><div><dt>Backoffice</dt><dd><span className={`status-chip ${data.backoffice_enabled ? "success" : "neutral"}`}>{data.backoffice_enabled ? "Aktif" : "Tidak aktif"}</span></dd></div><div><dt>Format unggahan</dt><dd>{data.formats.upload.join(", ")}</dd></div><div><dt>Format laporan</dt><dd>{data.formats.report.join(", ")}</dd></div></dl></section>
      <section className="panel settings-section"><header className="panel-header"><div><h2>Master referensi</h2><p>Identitas master wilayah yang sedang digunakan.</p></div></header><dl><div><dt>SHA-256</dt><dd className="mono hash-value">{data.reference.sha256}</dd></div><div><dt>Cakupan</dt><dd>{data.reference.cities} kota/kabupaten · {data.reference.districts} kecamatan · {data.reference.villages} kelurahan</dd></div></dl></section>
    </div>}
  </main>;
}
