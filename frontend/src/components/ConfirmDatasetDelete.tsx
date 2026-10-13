import { useEffect, useRef } from "react";
import type { DatasetSummary } from "../types";

export default function ConfirmDatasetDelete({ items, busy, error, onCancel, onConfirm }: {
  items: DatasetSummary[]; busy: boolean; error: string; onCancel: () => void; onConfirm: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const cancelButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const element = dialog.current;
    element?.showModal();
    cancelButton.current?.focus();
    return () => { element?.close(); if (previous?.isConnected) previous.focus(); };
  }, []);
  return <dialog ref={dialog} className="dataset-delete-dialog" aria-labelledby="delete-dataset-title" aria-describedby="delete-dataset-description" onCancel={(event) => { event.preventDefault(); if (!busy) onCancel(); }}>
    <h2 id="delete-dataset-title">Hapus {items.length === 1 ? "hasil assessment ini" : `${items.length} hasil assessment`}?</h2>
    <p id="delete-dataset-description">Dataset, temuan, dan laporan ini akan dihapus dari riwayat aktif. File sumber tetap tersimpan. Kamu bisa mengurungkan penghapusan.</p>
    <ul>{items.map((item) => <li key={item.id}>{item.original_filename}</li>)}</ul>
    {error && <p className="account-form-error" role="alert">{error}</p>}
    <footer><button ref={cancelButton} className="button secondary" type="button" disabled={busy} onClick={onCancel}>Batal</button><button className="button danger" type="button" disabled={busy} onClick={onConfirm}>{busy ? "Menghapus…" : `Hapus${items.length > 1 ? ` ${items.length} dataset` : " hasil"}`}</button></footer>
  </dialog>;
}
