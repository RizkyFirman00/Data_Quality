# Temuan dengan konteks sumber

Implemented:

- API grouped findings menyertakan source_record dari snapshot berdasarkan nomor sumber.
- Header baris menampilkan identitas dari kolom nama atau identifier yang dikenali; fallback tetap nomor sumber.
- Konteks menampilkan kegiatan/subkegiatan, periode/tahun dan satuan yang tersedia. Pemilihan kolom adalah heuristik nama, bukan pemahaman pasti tentang identitas dataset.
- Lihat baris lengkap meminta Preview berdasarkan source_row. Backend menentukan halaman berdasarkan posisi snapshot, termasuk Excel dengan baris kosong.
- Preview menandai baris dan menyediakan Kembali ke temuan, mempertahankan kategori dan disclosure baris.
- Ringkasan kategori memuat cakupan baris/kolom dan satu contoh dari finding asli.
- Anomali menampilkan evidence, arahan memeriksa kesebandingan kegiatan/periode/satuan, dan penjelasan batas confidence.

Partially implemented:

- Cakupan menampilkan pemeriksaan yang memiliki bukti temuan. Log pemeriksaan tanpa temuan, skipped dan failed belum tersimpan, sehingga tidak ditampilkan sebagai executed.
- Pemilihan identitas mendukung nama kolom yang dikenal; dataset lainnya tetap dapat membuka baris lengkap.

Verifikasi:

- 28 tes backend datasets API lulus.
- Tes baru menggunakan Excel dengan record di baris sumber 2 dan 40: grouped finding memuat konteks baris 40, Preview source_row=40 dengan page_size=1 mengembalikan page=2, nomor sumber 39 mengembalikan 404.
- Build frontend dan git diff --check lulus.
- Backend lokal direstart dan /api/health mengembalikan status ok.
- Pengujian browser interaksi terbaru belum selesai karena browser pengguna berubah tab saat automation mencoba mengakses halaman. Tidak ada klaim PASS click-through terbaru.

Arah visual mengikuti panel assessment navy, disclosure bukti dan komposisi perbandingan nilai yang telah disetujui. Tidak ada perubahan aturan deteksi atau nilai sumber.
