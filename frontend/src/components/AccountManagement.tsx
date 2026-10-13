import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { createUserAccount, listUserAccounts } from "../api";
import type { AccountRole, UserAccount } from "../types";
import { ChevronDownIcon } from "../icons";

export default function AccountManagement({ currentUserId }: { currentUserId: string }) {
  const [accounts, setAccounts] = useState<UserAccount[] | null>(null);
  const [loadError, setLoadError] = useState("");
  const [formError, setFormError] = useState("");
  const [success, setSuccess] = useState("");
  const [username, setUsername] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<AccountRole>("Pemeriksa");
  const [saving, setSaving] = useState(false);
  const requestSequence = useRef(0);
  const submitting = useRef(false);

  const load = useCallback(() => {
    const sequence = ++requestSequence.current;
    setLoadError("");
    listUserAccounts().then((result) => {
      if (sequence === requestSequence.current) setAccounts(result);
    }).catch((error) => {
      if (sequence === requestSequence.current) setLoadError(error instanceof Error ? error.message : "Daftar akun tidak dapat dimuat.");
    });
  }, []);
  useEffect(() => { load(); return () => { requestSequence.current++; }; }, [load]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting.current) return;
    submitting.current = true;
    setSaving(true); setFormError(""); setSuccess("");
    try {
      const account = await createUserAccount({ username: username.trim(), display_name: name.trim(), role });
      setSuccess(`Akun ${account.username} berhasil dibuat sebagai ${account.role}.`);
      setUsername(""); setName(""); setRole("Pemeriksa");
      load();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Akun belum dapat dibuat.");
    } finally {
      submitting.current = false;
      setSaving(false);
    }
  };

  return <section className="panel account-settings" aria-labelledby="account-settings-title">
    <header className="panel-header"><div><h2 id="account-settings-title">Akun pengguna</h2><p>Kelola akses Admin dan Pemeriksa.</p></div><span className="account-admin-label">Khusus Admin</span></header>
    <div className="account-settings-layout">
      <form className="account-create-form" onSubmit={submit}>
        <div className="account-form-heading"><h3>Buat akun baru</h3><p>Isi identitas dan tentukan aksesnya.</p></div>
        <fieldset disabled={saving}>
          <label htmlFor="account-name">Nama lengkap<input id="account-name" name="display_name" value={name} onChange={(event) => setName(event.target.value)} required maxLength={128} placeholder="Nama lengkap" autoComplete="off" /></label>
          <label htmlFor="account-username">Username<input id="account-username" name="new_username" value={username} onChange={(event) => setUsername(event.target.value)} required minLength={3} maxLength={64} pattern="[A-Za-z0-9._-]{3,64}" placeholder="contoh: pemeriksa.data" autoComplete="off" autoCapitalize="none" spellCheck={false} aria-describedby="account-username-help" /></label>
          <small id="account-username-help">3–64 karakter, tanpa spasi. Disimpan dalam huruf kecil.</small>
          <label htmlFor="account-role">Role<span className="account-role-select"><select id="account-role" name="role" value={role} onChange={(event) => setRole(event.target.value as AccountRole)}><option value="Pemeriksa">Pemeriksa</option><option value="Admin">Admin</option></select><ChevronDownIcon size={16} /></span></label>
          <p className="account-role-help">{role === "Admin" ? "Assessment dan kelola akun." : "Assessment saja, tanpa kelola akun."}</p>
        </fieldset>
        {formError && <p className="account-form-error" role="alert">{formError}</p>}
        {success && <p className="account-form-success" role="status">{success}</p>}
        <div className="account-create-footer"><div className="account-initial-password"><span>Password awal <code>Password123</code></span><small>Pengguna dapat menggantinya di Profil setelah login.</small></div><button className="button primary" type="submit" disabled={saving}>{saving ? "Membuat akun…" : "Buat akun"}</button></div>
      </form>
      <div className="account-list">
        <div className="account-list-heading"><h3>Akun terdaftar</h3>{accounts && <span>{accounts.length} akun</span>}</div>
        {loadError ? <div className="feedback error" role="alert"><div><strong>Daftar akun tidak dapat dimuat</strong><p>{loadError}</p></div><button className="button secondary" onClick={load}>Coba lagi</button></div>
          : accounts === null ? <p className="account-list-message" role="status">Memuat akun…</p>
          : accounts.length === 0 ? <p className="account-list-message">Belum ada akun. Buat akun melalui form di atas.</p>
          : <div className="account-table-wrap"><table className="account-table">
            <thead><tr><th scope="col">Nama pengguna</th><th scope="col">Username</th><th scope="col">Akses</th></tr></thead>
            <tbody>{accounts.map((account) => <tr key={account.id}>
              <td><strong>{account.display_name}</strong>{account.id === currentUserId && <small className="account-self">Anda</small>}<span className="account-mobile-username">@{account.username}</span></td>
              <td className="account-username">@{account.username}</td>
              <td><span className={`account-role-badge ${account.role === "Admin" ? "admin" : "examiner"}`}>{account.role}</span>{!account.is_active && <small className="account-self">Nonaktif</small>}</td>
            </tr>)}</tbody>
          </table></div>}
      </div>
    </div>
  </section>;
}
