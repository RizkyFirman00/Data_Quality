import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import DashboardPage from "./pages/DashboardPage";
import DatasetDetailPage from "./pages/DatasetDetailPage";
import DatasetsPage from "./pages/DatasetsPage";
import UploadDatasetPage from "./pages/UploadDatasetPage";
import FindingsPage from "./pages/FindingsPage";
import ReferenceDataPage from "./pages/ReferenceDataPage";
import SettingsPage from "./pages/SettingsPage";
import LoginPage from "./pages/LoginPage";
import ProfilePage from "./pages/ProfilePage";
import { getCurrentUser, logoutLocal } from "./api";
import type { AuthSession } from "./types";
import {
  ArrowLeftIcon,
  BrandLogo,
  CheckIcon,
  DashboardNavIcon,
  DatasetsNavIcon,
  FindingsNavIcon,
  PlusIcon,
  PeopleNavIcon,
  LogoutIcon,
  ReferenceNavIcon,
  SettingsNavIcon,
  ShieldCheckIcon,
} from "./icons";
import "./styles.css";

export default function App() {
  const [auth, setAuth] = useState<AuthSession | null | undefined>(undefined);
  const [menuOpen, setMenuOpen] = useState(false);
  const [authNotice, setAuthNotice] = useState("");
  const location = useLocation();
  useEffect(() => setMenuOpen(false), [location.pathname]);
  useEffect(() => {
    getCurrentUser().then(setAuth).catch(() => setAuth(null));
    const expired = () => setAuth(null);
    window.addEventListener("auth-expired", expired);
    return () => window.removeEventListener("auth-expired", expired);
  }, []);

  if (auth === undefined) return <main className="auth-loading" role="status"><span className="spinner" /><p>Memeriksa session…</p></main>;
  if (auth === null) return <LoginPage notice={authNotice} onLogin={(session) => { setAuthNotice(""); setAuth(session); }} />;

  const logout = async () => { try { await logoutLocal(); } finally { setAuthNotice(""); setAuth(null); } };

  return (
    <div className="app-shell">
      <button className={`nav-scrim ${menuOpen ? "visible" : ""}`} aria-label="Tutup navigasi" onClick={() => setMenuOpen(false)} />
      <aside className={`sidebar ${menuOpen ? "open" : ""}`}>
        <div className="brand"><BrandLogo size={34} /><div><strong>Data Quality</strong><span>Assessment dataset</span></div></div>
        <NavLink className="new-assessment" to="/datasets/new"><PlusIcon size={16} /> Assessment baru</NavLink>
        <nav aria-label="Navigasi utama">
          <NavLink to="/dashboard" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}><DashboardNavIcon size={20} />Ringkasan</NavLink>
          <NavLink to="/datasets" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}><DatasetsNavIcon size={20} />Dataset</NavLink>
          <NavLink to="/findings" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}><FindingsNavIcon size={20} />Temuan</NavLink>
          <NavLink to="/reference-data" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}><ReferenceNavIcon size={20} />Data referensi</NavLink>
          <NavLink to="/settings" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}><SettingsNavIcon size={20} />Pengaturan</NavLink>
        </nav>
        <p className="source-promise"><span aria-hidden="true"><ShieldCheckIcon size={15} /></span>Sumber data tidak pernah diubah</p>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <button className="menu-button" type="button" aria-label="Buka navigasi" aria-expanded={menuOpen} onClick={() => setMenuOpen(true)}><span /><span /><span /></button>
          <NavLink to="/profile" className="topbar-profile" aria-label="Buka profil akun"><PeopleNavIcon size={22} /><span><strong>{auth.user.display_name}</strong><small>Profil · @{auth.user.username}</small></span></NavLink>
          <div className="account-menu"><button type="button" onClick={logout}><LogoutIcon size={16} />Logout</button></div>
        </header>
        <Routes>
          <Route path="/dashboard" element={<DashboardPage isAdmin={auth.user.is_admin} />} />
          <Route path="/datasets" element={<DatasetsPage isAdmin={auth.user.is_admin} />} />
          <Route path="/datasets/new" element={<UploadDatasetPage />} />
          <Route path="/datasets/:datasetId" element={<DatasetDetailPage />} />
          <Route path="/findings" element={<FindingsPage />} />
          <Route path="/reference-data" element={<ReferenceDataPage />} />
          <Route path="/settings" element={<SettingsPage user={auth.user} />} />
          <Route path="/profile" element={<ProfilePage user={auth.user} onPasswordChanged={(message) => { setAuthNotice(message); setAuth(null); }} />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </div>
    </div>
  );
}
