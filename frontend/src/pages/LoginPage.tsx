import { FormEvent, useState } from "react";
import { ApiError, loginLocal } from "../api";
import type { AuthSession } from "../types";
import { BrandLogo } from "../icons";

export default function LoginPage({ onLogin }: { onLogin: (session: AuthSession) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true); setError("");
    try { onLogin(await loginLocal(username, password)); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "Login tidak dapat diproses."); }
    finally { setBusy(false); }
  };
  return <main className="login-page">
    <section className="login-panel" aria-labelledby="login-title">
      <div className="login-brand"><BrandLogo size={40} /><div><strong>Data Quality</strong><span>Assessment dataset</span></div></div>
      <div className="login-copy"><span className="eyebrow">Akses pemeriksa</span><h1 id="login-title">Masuk ke ruang kerja</h1><p>Gunakan akun lokal yang dibuat oleh administrator sistem.</p></div>
      <form className="login-form" onSubmit={submit}>
        <label><span>Username</span><input name="username" autoComplete="username" autoCapitalize="none" spellCheck={false} value={username} onChange={(event) => setUsername(event.target.value)} required minLength={3} maxLength={64} autoFocus /></label>
        <label><span>Password</span><input name="password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required maxLength={128} /></label>
        {error && <div className="login-error" role="alert">{error}</div>}
        <button className="button primary login-button" disabled={busy}>{busy ? "Memeriksa akun…" : "Masuk"}</button>
      </form>
      <p className="login-help">Belum memiliki akun? Hubungi administrator aplikasi.</p>
    </section>
    <aside className="login-context" aria-label="Perlindungan data sumber">
      <div><span>PRINSIP KERJA</span><h2>Temuan terlihat.<br />Sumber tetap utuh.</h2><p>Sistem memeriksa salinan kerja dan menyimpan evidence tanpa mengoreksi dataset asli secara otomatis.</p></div>
      <dl><div><dt>01</dt><dd>Dataset sumber tidak diubah</dd></div><div><dt>02</dt><dd>Rekomendasi perlu diverifikasi</dd></div><div><dt>03</dt><dd>Akses dibatasi per session</dd></div></dl>
    </aside>
  </main>;
}
