import { Fragment, useCallback, useDeferredValue, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, listGlobalFindings } from "../api";
import { ArrowLeftIcon, ArrowRightIcon, CheckIcon, ChevronDownIcon, SearchIcon } from "../icons";
import { formatIssueLabel, type GlobalFindingPage } from "../types";

const value = (item: unknown) => (item == null ? "—" : typeof item === "object" ? JSON.stringify(item) : String(item));

export default function FindingsPage() {
  const [data, setData] = useState<GlobalFindingPage | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [severity, setSeverity] = useState("");
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    listGlobalFindings({ page, pageSize: 50, search: deferredSearch || undefined, severity: severity || undefined })
      .then(setData)
      .catch((reason) => setError(reason instanceof ApiError ? reason : new ApiError("Temuan tidak dapat dimuat.")));
  }, [deferredSearch, page, severity]);

  useEffect(load, [load]);
  const pages = Math.max(1, Math.ceil((data?.total || 0) / 50));

  return (
    <main className="page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">Temuan</span>
          <h1>Temuan lintas dataset</h1>
          <p>Daftar error bersifat read-only dan diurutkan per assessment lalu baris sumber.</p>
        </div>
      </div>
      <section className="panel">
        <header className="panel-header dataset-toolbar">
          <div>
            <h2>Semua temuan</h2>
            <p>{data ? `${data.total.toLocaleString("id-ID")} temuan` : "Memuat temuan…"}</p>
          </div>
          <div className="filter-controls">
            <label className="search-field">
              <span className="sr-only">Cari temuan</span>
              <SearchIcon size={16} />
              <input
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value);
                  setPage(1);
                  setExpanded(null);
                }}
                placeholder="Cari dataset, kolom, atau nilai"
              />
            </label>
            <select
              aria-label="Filter severity"
              value={severity}
              onChange={(event) => {
                setSeverity(event.target.value);
                setPage(1);
                setExpanded(null);
              }}
            >
              <option value="">Semua severity</option>
              <option value="HIGH">Tinggi</option>
              <option value="MEDIUM">Medium</option>
            </select>
          </div>
        </header>

        {error ? (
          <div className="feedback error inset">
            <div>
              <strong>Temuan tidak dapat dimuat</strong>
              <p>{error.message}</p>
            </div>
            <button className="button secondary" onClick={load}>
              Coba lagi
            </button>
          </div>
        ) : !data ? (
          <div className="table-skeleton">
            <i />
            <i />
            <i />
          </div>
        ) : data.total === 0 ? (
          <div className="empty-state compact">
            <span aria-hidden="true">
              <CheckIcon size={20} />
            </span>
            <h3>Tidak ada temuan</h3>
            <p>Belum ada error yang cocok dengan filter.</p>
          </div>
        ) : (
          <>
            <div className="table-wrap global-findings">
              <table>
                <thead>
                  <tr>
                    <th>Dataset</th>
                    <th>Baris</th>
                    <th>Kolom</th>
                    <th>Temuan</th>
                    <th>Nilai saat ini</th>
                    <th>Rekomendasi</th>
                    <th>
                      <span className="sr-only">Detail</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((item) => (
                    <Fragment key={item.id}>
                      <tr>
                        <td>
                          <Link className="table-link" to={`/datasets/${item.dataset_id}`}>
                            {item.dataset_name}
                          </Link>
                        </td>
                        <td className="row-number">{item.row}</td>
                        <td className="column-name">{item.column || "—"}</td>
                        <td className="finding-issue-cell">
                          <strong className="finding-title">{formatIssueLabel(item.issue_type)}</strong>
                          <span className={`severity-chip ${item.severity.toLowerCase()}`}>
                            {item.severity === "HIGH" ? "Tinggi" : "Medium"}
                          </span>
                        </td>
                        <td className="finding-value">
                          {item.original_value == null ? (
                            <span className="muted-value">—</span>
                          ) : (
                            <code>{value(item.original_value)}</code>
                          )}
                        </td>
                        <td className="finding-value">
                          {item.expected_value == null ? (
                            <span className="muted-value">—</span>
                          ) : (
                            <code>{value(item.expected_value)}</code>
                          )}
                        </td>
                        <td>
                          <button
                            className="disclosure"
                            aria-expanded={expanded === item.id}
                            aria-label={`${expanded === item.id ? "Tutup" : "Buka"} detail temuan baris ${item.row}`}
                            onClick={() => setExpanded(expanded === item.id ? null : item.id)}
                          >
                            <ChevronDownIcon size={16} />
                          </button>
                        </td>
                      </tr>
                      {expanded === item.id && (
                        <tr className="finding-detail-row">
                          <td colSpan={7}>
                            <div>
                              <section>
                                <span>Evidence</span>
                                <p>{item.evidence || "—"}</p>
                              </section>
                              <section>
                                <span>Rekomendasi tindakan</span>
                                <p>{item.recommendation || "—"}</p>
                              </section>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
            <footer className="pagination">
              <span>
                Halaman {page} dari {pages}
              </span>
              <div>
                <button
                  className="icon-button"
                  disabled={page === 1}
                  onClick={() => {
                    setPage(page - 1);
                    setExpanded(null);
                  }}
                  aria-label="Halaman sebelumnya"
                >
                  <ArrowLeftIcon size={16} />
                </button>
                <button
                  className="icon-button"
                  disabled={page >= pages}
                  onClick={() => {
                    setPage(page + 1);
                    setExpanded(null);
                  }}
                  aria-label="Halaman berikutnya"
                >
                  <ArrowRightIcon size={16} />
                </button>
              </div>
            </footer>
          </>
        )}
      </section>
    </main>
  );
}
