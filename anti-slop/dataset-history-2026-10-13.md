# Riwayat dataset per akun dan penghapusan

IMPLEMENTED: ownership berbasis akun pada assessment baru, pembatasan akses semua endpoint dataset untuk Pemeriksa, akses seluruh dataset bagi Admin, pagination/filter server-side, swipe dua tahap, konfirmasi dan hapus massal per halaman, pemulihan operasi terakhir.

Dataset legacy tetap owner_id null dan hanya terlihat Admin. Penghapusan bersifat recoverable melalui deleted_at; source file, snapshot, profiling, dan findings tidak dihapus permanen. Tidak menambah status reviewer atau mengubah mekanisme assessment.

Direction: mengikuti lembar assessment navy/putih yang disetujui, ENERGY 1 / RHYTHM 1 / MOTION 1. Checkbox untuk seleksi nyata, warna merah hanya pada aksi destruktif setelah swipe, tidak pada header atau tombol permanen. Dialog memisahkan konfirmasi dari gesture; gerakan hanya menunjukkan progres swipe. Penyesuaian layout memakai lebar panel agar sidebar tidak membuat tabel terpotong pada tablet.

## Evidence

- Backend PASS: 207 tests. Sebelas tes tambahan mencakup isolasi dua Pemeriksa, Admin semua data, legacy admin-only, detail/preview/findings/comparison/CSV-XLSX-PDF, penolakan parent asing, pagination/filter/bounds, bulk atomic permission validation, processing guard, auth/CSRF, pemulihan dan file source tetap identik, serta parent dihapus tidak merusak child.
- Frontend PASS: TypeScript/Vite build dan 10 tests. Termasuk kontrak pagination/bulk CSRF serta threshold closed/reveal/confirm dan pointer cancellation.
- Migrasi PostgreSQL lokal PASS: alembic 0006 -> 0007; head diverifikasi dan health status ok.
- Browser desktop PASS: pagination mengubah record 1–20 ke 21–40 dari 169 dataset nyata, kemudian dikembalikan ke halaman pertama.
- Browser desktop PASS: swipe pendek menampilkan Hapus; swipe lanjut membuka dialog satu dataset tanpa menavigasi tautan; Escape membatalkan.
- Browser desktop PASS: pilih halaman menandai 20 record, Hapus terpilih membuka dialog 20 dataset, Escape membatalkan. Tidak mengonfirmasi penghapusan live.
- Browser desktop PASS: header tidak lagi berwarna merah dan ikon hapus permanen di kanan tidak ada, mengikuti koreksi pengguna.

## Batas verifikasi

Mobile/touch fisik, seluruh state error/loading, dan pemulihan melalui UI live belum diuji. Penghapusan dan restore sukses diuji dalam database SQLite terpisah; tidak ada dataset aktif yang dihapus oleh agent. Gesture mouse desktop dan helper threshold bukan bukti gesture touch fisik. Sidebar sesi Admin dipertahankan; user sempat berpindah tab sehingga beberapa tes UI dihentikan lalu diulang dengan keadaan browser terbaru.
