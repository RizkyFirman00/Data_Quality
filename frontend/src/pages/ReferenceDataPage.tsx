import { useCallback, useDeferredValue, useEffect, useState } from "react";
import { ApiError, getReferenceData } from "../api";
import { ArrowLeftIcon, ArrowRightIcon, SearchIcon } from "../icons";
import type { ReferencePage } from "../types";

export default function ReferenceDataPage() {
  const [data, setData] = useState<ReferencePage | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [page, setPage] = useState(1);
  const load = useCallback(() => {
    setError(null);
    getReferenceData({ page, pageSize: 50, search: deferredSearch || undefined }).then(setData)
      .catch((reason) => setError(reason instanceof ApiError ? reason : new ApiError("Data referensi tidak dapat dimuat.")));
  }, [deferredSearch, page]);
  useEffect(load, [load]);
  const pages = Math.max(1, Math.ceil((data?.total || 0) / 50));
  return <main className="page">
    <div className="page-heading"><div><span className="eyebrow">Referensi</span><h1>Master wilayah DKI Jakarta</h1><p>Referensi deterministik yang dipakai untuk memeriksa nama, kode, dan hierarki wilayah.</p></div></div>
    {data && <section className="summary-strip"><div><span>Kota/Kabupaten</span><strong>{data.summary.cities}</strong></div><div><span>Kecamatan</span><strong>{data.summary.districts}</strong></div><div><span>Kelurahan</span><strong>{data.summary.villages}</strong></div><div><span>Versi master</span><strong className="text-value mono">{data.summary.sha256.slice(0, 12)}</strong></div></section>}
    <section className="panel"><header className="panel-header dataset-toolbar"><div><h2>Daftar hierarki wilayah</h2><p>{data ? `${data.total.toLocaleString("id-ID")} kelurahan ditampilkan` : "Memuat master…"}</p></div><label className="search-field"><span className="sr-only">Cari wilayah</span><SearchIcon size={16} /><input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Cari nama atau kode wilayah" /></label></header>
      {error ? <div className="feedback error inset"><div><strong>Referensi tidak dapat dimuat</strong><p>{error.message}</p></div><button className="button secondary" onClick={load}>Coba lagi</button></div> : !data ? <div className="table-skeleton"><i /><i /><i /></div> : <><div className="table-wrap reference-table"><table><thead><tr><th>Kota/Kabupaten</th><th>Kecamatan</th><th>Kelurahan</th></tr></thead><tbody>{data.items.map((row) => <tr key={row.village_code}><td><strong>{row.city_name}</strong><small>{row.city_code}</small></td><td><strong>{row.district_name}</strong><small>{row.district_code}</small></td><td><strong>{row.village_name}</strong><small>{row.village_code}</small></td></tr>)}</tbody></table></div><footer className="pagination"><span>Halaman {page} dari {pages}</span><div><button className="icon-button" disabled={page === 1} onClick={() => setPage(page - 1)} aria-label="Halaman sebelumnya"><ArrowLeftIcon size={16} /></button><button className="icon-button" disabled={page >= pages} onClick={() => setPage(page + 1)} aria-label="Halaman berikutnya"><ArrowRightIcon size={16} /></button></div></footer></>}
    </section>
  </main>;
}
