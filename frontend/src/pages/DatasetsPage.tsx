import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, deleteDatasets, getDatasetPage, restoreDatasets } from "../api";
import { ArrowLeftIcon, ArrowRightIcon, PlusIcon, SearchIcon, TrashIcon } from "../icons";
import type { DatasetPage, DatasetSummary } from "../types";
import SwipeDatasetRow from "../components/SwipeDatasetRow";
import ConfirmDatasetDelete from "../components/ConfirmDatasetDelete";

export default function DatasetsPage({ isAdmin = false }: { isAdmin?: boolean }) {
  const [data, setData] = useState<DatasetPage | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("ALL");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirmation, setConfirmation] = useState<DatasetSummary[] | null>(null);
  const [mutationError, setMutationError] = useState("");
  const [busy, setBusy] = useState(false);
  const [undo, setUndo] = useState<string[]>([]);
  const [message, setMessage] = useState("");
  const sequence = useRef(0);
  const submitting = useRef(false);
  const selectPage = useRef<HTMLInputElement>(null);

  useEffect(() => { if (search === query) return; const timer = window.setTimeout(() => { setQuery(search); setPage(1); setSelected(new Set()); }, 250); return () => window.clearTimeout(timer); }, [search, query]);
  const load = useCallback(() => {
    const request = ++sequence.current;
    setError(null); setData(null); setSelected(new Set());
    getDatasetPage(page, pageSize, query, status).then((result) => {
      if (request !== sequence.current) return;
      const last = Math.max(1, Math.ceil(result.total / pageSize));
      if (page > last) { setPage(last); return; }
      setData(result);
    }).catch((reason) => { if (request === sequence.current) setError(reason instanceof ApiError ? reason : new ApiError("Riwayat dataset tidak dapat dimuat.")); });
  }, [page, pageSize, query, status]);
  useEffect(() => { load(); return () => { sequence.current++; }; }, [load]);
  const selectable = data?.items.filter((item) => item.status !== "PROCESSING") || [];
  const allSelected = selectable.length > 0 && selectable.every((item) => selected.has(item.id));
  useEffect(() => { if (selectPage.current) selectPage.current.indeterminate = selected.size > 0 && !allSelected; }, [selected, allSelected]);
  const pages = Math.max(1, Math.ceil((data?.total || 0) / pageSize));
  const changePage = (value: number) => { setSelected(new Set()); setPage(value); };
  const askDelete = (items: DatasetSummary[]) => { setMutationError(""); setConfirmation(items); };
  const remove = async () => {
    if (!confirmation || submitting.current) return;
    submitting.current = true; setBusy(true); setMutationError("");
    try {
      const result = await deleteDatasets(confirmation.map((item) => item.id));
      setUndo(result.dataset_ids); setMessage(`${result.count} hasil assessment dihapus dari riwayat.`);
      setConfirmation(null); setSelected(new Set()); load();
    } catch (reason) { setMutationError(reason instanceof Error ? reason.message : "Hasil assessment belum dapat dihapus."); }
    finally { submitting.current = false; setBusy(false); }
  };
  const restore = async () => {
    if (submitting.current || undo.length === 0) return;
    submitting.current = true; setBusy(true); setMutationError("");
    try { const result = await restoreDatasets(undo); setUndo([]); setMessage(`${result.count} hasil assessment dipulihkan.`); load(); }
    catch (reason) { setMutationError(reason instanceof Error ? reason.message : "Dataset belum dapat dipulihkan."); }
    finally { submitting.current = false; setBusy(false); }
  };

  return <main className="page dataset-history-page">
    <div className="page-heading"><div><span className="eyebrow">Dataset</span><h1>Riwayat assessment</h1><p>{isAdmin ? "Seluruh hasil assessment, termasuk dataset milik pengguna lain." : "Dataset dan hasil pemeriksaan yang kamu unggah."}</p></div><Link className="button primary" to="/datasets/new"><PlusIcon size={16} /> Assessment baru</Link></div>
    {message && <div className="dataset-delete-feedback" role="status"><span>{message}</span>{undo.length > 0 && <button type="button" disabled={busy} onClick={restore}>{busy ? "Memulihkan…" : "Urungkan"}</button>}</div>}
    {mutationError && !confirmation && <p className="account-form-error" role="alert">{mutationError}</p>}
    <section className="panel dataset-panel" aria-labelledby="dataset-title">
      <header className="panel-header dataset-toolbar"><div><h2 id="dataset-title">{isAdmin ? "Semua dataset" : "Dataset saya"}</h2><p>{data ? `${data.total.toLocaleString("id-ID")} assessment${query || status !== "ALL" ? " cocok dengan filter" : " tersimpan"}` : "Memuat riwayat…"}</p></div><div className="filter-controls"><label className="search-field"><span className="sr-only">Cari dataset</span><SearchIcon size={16} /><input name="dataset-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Cari nama dataset" /></label><label><span className="sr-only">Filter status</span><select name="dataset-status" value={status} onChange={(event) => { setStatus(event.target.value); changePage(1); }}><option value="ALL">Semua status</option><option value="PASSED">Tanpa temuan prioritas tinggi</option><option value="NEEDS_CORRECTION">Perlu koreksi</option><option value="PROCESSING">Diproses</option><option value="FAILED">Gagal</option></select></label></div></header>
      <div className="dataset-selection-toolbar"><label className="dataset-select-all"><input ref={selectPage} type="checkbox" checked={allSelected} disabled={!selectable.length || busy} onChange={() => setSelected(allSelected ? new Set() : new Set(selectable.map((item) => item.id)))} />{selected.size ? `${selected.size} dipilih di halaman ini` : "Pilih halaman ini"}</label>{selected.size > 0 ? <div><button type="button" className="button secondary" onClick={() => setSelected(new Set())}>Batal pilih</button><button type="button" className="button danger" disabled={busy} onClick={() => askDelete((data?.items || []).filter((item) => selected.has(item.id)))}><TrashIcon size={16} />Hapus terpilih</button></div> : <small>Geser kiri untuk menampilkan Hapus. Geser lebih jauh untuk konfirmasi.</small>}</div>
      <span id="dataset-swipe-keyboard-help" className="sr-only">Saat baris fokus, panah kiri menampilkan tombol Hapus. Panah kanan atau Escape menutupnya.</span>
      {error ? <div className="feedback error inset" role="alert"><div><strong>Riwayat tidak dapat dimuat</strong><p>{error.message}</p></div><button className="button secondary" onClick={load}>Coba lagi</button></div>
        : !data ? <div className="table-skeleton" role="status" aria-label="Memuat riwayat"><i /><i /><i /><i /></div>
        : data.total === 0 ? <div className="empty-state compact"><h3>{query || status !== "ALL" ? "Dataset tidak ditemukan" : "Belum ada dataset"}</h3><p>{query || status !== "ALL" ? "Ubah kata pencarian atau filter status." : "Unggah CSV, XLSX, atau XLS untuk mulai memeriksa data."}</p>{query || status !== "ALL" ? <button className="button secondary" onClick={() => { setSearch(""); setQuery(""); setStatus("ALL"); changePage(1); }}>Hapus filter</button> : <Link className="button primary" to="/datasets/new">Mulai assessment</Link>}</div>
        : <div className="dataset-table" role="table" aria-label="Riwayat assessment"><div className="dataset-history-head" role="row"><span className="dataset-select-cell" role="columnheader"><span className="sr-only">Pilih dataset</span></span><div className="dataset-table-head"><span role="columnheader">Dataset</span><span role="columnheader">Format</span><span role="columnheader">Dimensi</span><span role="columnheader">Temuan</span><span role="columnheader">Diunggah</span><span role="columnheader">Status</span><span /></div></div>{data.items.map((item) => <SwipeDatasetRow key={`${page}-${item.id}`} item={item} isAdmin={isAdmin} selected={selected.has(item.id)} onSelect={() => setSelected((current) => { const next = new Set(current); next.has(item.id) ? next.delete(item.id) : next.add(item.id); return next; })} onDelete={() => askDelete([item])} />)}</div>}
      <footer className="pagination dataset-history-pagination"><span>{data?.total ? `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, data.total)} dari ${data.total.toLocaleString("id-ID")} dataset` : "0 dataset"}</span><div><label>Per halaman <select value={pageSize} disabled={busy} onChange={(event) => { setPageSize(Number(event.target.value)); changePage(1); }}><option value={10}>10</option><option value={20}>20</option><option value={50}>50</option></select></label><button type="button" className="icon-button" disabled={!data || page <= 1 || busy} onClick={() => changePage(page - 1)} aria-label="Halaman sebelumnya"><ArrowLeftIcon size={16} /></button><span>{page} / {pages}</span><button type="button" className="icon-button" disabled={!data || page >= pages || busy} onClick={() => changePage(page + 1)} aria-label="Halaman berikutnya"><ArrowRightIcon size={16} /></button></div></footer>
    </section>
    {confirmation && <ConfirmDatasetDelete items={confirmation} busy={busy} error={mutationError} onCancel={() => { if (!busy) setConfirmation(null); }} onConfirm={remove} />}
  </main>;
}
