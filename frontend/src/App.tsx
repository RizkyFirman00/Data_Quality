import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import DatasetDetailPage from "./pages/DatasetDetailPage";
import DatasetsPage from "./pages/DatasetsPage";
import UploadDatasetPage from "./pages/UploadDatasetPage";
import "./styles.css";

function Mark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <span>DQ</span>
    </span>
  );
}

export default function App() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <Mark />
          <div>
            <strong>Data Quality</strong>
            <span>Pemprov DKI Jakarta</span>
          </div>
        </div>
        <nav aria-label="Navigasi utama">
          <NavLink to="/datasets" className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16" /></svg>
            Dataset
          </NavLink>
        </nav>
        <div className="phase-note">
          <span>FASE 04</span>
          <p>Standar format tanggal</p>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="mobile-brand"><Mark /><strong>Data Quality</strong></div>
          <span className="environment"><i /> Lingkungan lokal</span>
        </header>
        <Routes>
          <Route path="/datasets" element={<DatasetsPage />} />
          <Route path="/datasets/new" element={<UploadDatasetPage />} />
          <Route path="/datasets/:datasetId" element={<DatasetDetailPage />} />
          <Route path="*" element={<Navigate to="/datasets" replace />} />
        </Routes>
      </div>
    </div>
  );
}
