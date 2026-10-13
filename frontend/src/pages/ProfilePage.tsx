import { useRef, useState, type FormEvent } from "react";
import { changeOwnPassword } from "../api";
import type { LocalUser } from "../types";

export default function ProfilePage({ user, onPasswordChanged }: { user: LocalUser; onPasswordChanged: (message: string) => void }) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const submitting = useRef(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting.current) return;
    setError("");
    if (newPassword !== confirmation) { setError("Konfirmasi password baru tidak cocok."); return; }
    if (newPassword === currentPassword) { setError("Password baru harus berbeda dari password saat ini."); return; }
    submitting.current = true; setSaving(true);
    try {
      const result = await changeOwnPassword({ current_password: currentPassword, new_password: newPassword, confirm_password: confirmation });
      setCurrentPassword(""); setNewPassword(""); setConfirmation("");
      onPasswordChanged(result.message);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Password belum dapat diubah.");
    } finally {
      submitting.current = false; setSaving(false);
    }
  };

  return <main className="page narrow user-profile-page">
    <div className="page-heading"><div><span className="eyebrow">Profil</span><h1>Akun saya</h1><p>Informasi akun dan keamanan aksesmu.</p></div></div>
    <section className="panel user-profile-identity" aria-label="Informasi akun"><dl><div><dt>Nama</dt><dd>{user.display_name}</dd></div><div><dt>Username</dt><dd>@{user.username}</dd></div><div><dt>Role</dt><dd>{user.is_admin ? "Admin" : "Pemeriksa"}</dd></div></dl></section>
    <section className="panel profile-security" aria-labelledby="profile-password-title">
      <header className="panel-header"><div><h2 id="profile-password-title">Ganti password</h2><p>Gunakan password pribadi untuk menggantikan password awal.</p></div></header>
      <form className="profile-password-form" onSubmit={submit}>
        <fieldset disabled={saving}>
          <label className="profile-current-password" htmlFor="profile-current-password">Password saat ini<input id="profile-current-password" name="current_password" type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required maxLength={128} /></label>
          <label htmlFor="profile-new-password">Password baru<input id="profile-new-password" name="new_password" type="password" autoComplete="new-password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required minLength={12} maxLength={128} aria-describedby="profile-password-help" /></label>
          <label htmlFor="profile-confirm-password">Konfirmasi password baru<input id="profile-confirm-password" name="confirm_password" type="password" autoComplete="new-password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} required minLength={12} maxLength={128} /></label>
        </fieldset>
        <p id="profile-password-help" className="profile-password-help">12–128 karakter dan berbeda dari password saat ini. Jangan gunakan password yang sama dengan akun lain.</p>
        {error && <p className="account-form-error" role="alert">{error}</p>}
        <footer><p>Setelah berhasil, semua sesi akun ini akan keluar. Kamu perlu login kembali dengan password baru.</p><button className="button primary" type="submit" disabled={saving}>{saving ? "Menyimpan…" : "Simpan password"}</button></footer>
      </form>
    </section>
  </main>;
}
