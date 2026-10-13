# Audit UI/UX dan mekanisme assessment, tahap 1

Target: localhost:5173, termasuk dataset `52814f91-3fe4-42eb-bdf4-3b6fae820d53`.
Tanggal: 13 Oktober 2026.
Scope: seluruh halaman utama yang telah terautentikasi, ketepatan presentasi temuan, dan kontrak pemeriksaan berdasarkan agents.md. Tidak mengubah data asli atau menjalankan ulang assessment tersimpan.

## Ringkasan

13 kelompok masalah dikoreksi: 5 High, 6 Medium, 2 Low. Ini bukan pernyataan bahwa seluruh web bebas bug atau seluruh deteksi telah divalidasi ilmiah.

| ID | Masalah | Severity | Kategori | Status |
|---|---|---|---|---|
| 1 | Periode triwulan/semester valid ditolak | High | Ketepatan deteksi | IMPLEMENTED |
| 2 | Rencana pemeriksaan hanya label, detektor tidak digate | High | Mekanisme adaptif | IMPLEMENTED untuk deterministik/statistik |
| 3 | Nilai asli temuan semantik kehilangan whitespace | High | Provenance | IMPLEMENTED |
| 4 | Confidence semantik rendah/boolean diterima | High | Reliabilitas LLM | IMPLEMENTED |
| 5 | Konversi IQR ke float dapat overflow | High | Ketepatan deteksi | IMPLEMENTED |
| 6 | Lulus terkesan bebas masalah meski masih ada temuan | Medium | Konten/UX | IMPLEMENTED |
| 7 | Badge Preview menampilkan 50 sampel, bukan 884 baris | Medium | Konten | IMPLEMENTED |
| 8 | Respons lama dapat menggantikan pencarian/preview baru | Medium | Functional | IMPLEMENTED, inspeksi kode |
| 9 | Pencarian referensi kosong tanpa tindakan pemulihan | Medium | UX | IMPLEMENTED, browser verified |
| 10 | Nilai null/kosong disamarkan dalam temuan lintas dataset | Medium | Evidence/UX | IMPLEMENTED |
| 11 | Tombol laporan mobile bertumpuk dan terbalik | Medium | Visual | IMPLEMENTED, 390 px verified |
| 12 | Ketidakkonsistenan skala visual ant halaman | Low | Visual | IMPLEMENTED untuk fondasi bersama |
| 13 | Field pencarian/filter tidak punya name/id | Low | Browser warning | IMPLEMENTED, reload verified |

## Detail masalah dan reproduksi

### 1. Periode statistik valid ditolak

- Lokasi: backend/app/quality.py, assessment unggahan CSV/Excel.
- Reproduksi: nilai `2025-T1` atau `2025-S1` pada `periode_data`.
- Sebelum: INVALID_DATE_FORMAT karena hanya YYYY/YYYYMM diterima.
- Sesudah: T1–T4 dan S1–S2 diterima; tahun 0000, T0/T5, S3, bulan 00/13 tetap ditolak. Nilai asli tidak diubah. Periode yang sudah deterministik dikenali tidak dikirim untuk penafsiran role/typo LLM.
- Bukti: test_date_quality.py dan test_period_semantic.py.

### 2. Seleksi adaptif tidak mengendalikan eksekusi

- Lokasi: backend/app/quality.py, datasets.py, workflow.py; /datasets/new.
- Reproduksi: dataset teks saja memanggil seluruh keluarga detektor; numeric-only juga dapat kehilangan rencana kalkulasi karena menghitung jumlah jenis role, bukan kolom.
- Sesudah: dispatcher memilih detektor dari profil efektif, memisahkan CALCULATION dan CROSS_FIELD. IQR dipilih jika ada measure numerik dan minimal 8 baris. Hint tanggal yang eksplisit tetap dipilih meskipun seluruh nilainya invalid.
- Assessment baru menyimpan available/relevant/executed/skipped dan alasan skip di source_metadata.quality_checks. Log ini tidak ditambahkan secara retroaktif ke assessment lama.
- Bukti: test_adaptive_checks.py memonkeypatch seluruh detektor tidak relevan agar test gagal jika salah satunya dipanggil; API test memeriksa metadata tersimpan.
- Batas: metadata tersebut hanya deterministik/statistik. Log kegagalan dan jumlah kandidat semantik per langkah belum lengkap.

### 3. Nilai asli semantik terpotong

- Reproduksi: teks `  Festival Jakrta  ` menjadi kandidat typo.
- Sebelum: original_value disimpan tanpa spasi awal/akhir.
- Sesudah: normalisasi kandidat tidak menggantikan nilai sumber pada finding.
- Bukti: test_semantic_uses_llm_for_bounded_free_text_typo mengassert whitespace asli.

### 4. Confidence LLM tidak difilter secara memadai

- Reproduksi: provider mengembalikan confidence 0.1, 0.79, true, atau NaN.
- Sebelum: nilai rendah dapat dipublikasikan; true dikonversi menjadi 1.0.
- Sesudah: temuan semantik mensyaratkan confidence 0.8–1 dan bukan boolean. Role dan action-summary juga menolak boolean.
- Bukti: test_semantic_does_not_publish_low_or_invalid_confidence, serta suite fallback existing.
- Batas: 0.8 adalah kebijakan operasional awal, bukan threshold hasil eksperimen ground truth. Provider diuji dengan mock, bukan panggilan live.

### 5. IQR overflow

- Reproduksi: angka 400 digit pada measure numerik bersama minimal 8 nilai lain.
- Sebelum: konversi float bisa menghasilkan infinity atau exception; kuartil/batas dapat tidak valid.
- Sesudah: IQR menggunakan Decimal, menjaga angka besar tetap dapat diperiksa tanpa infinity.
- Bukti: test_statistical_checks_handle_large_numbers_without_float_overflow, termasuk angka string dan integer.

### 6. Label status dan ringkasan menyesatkan

- Lokasi: /dashboard, /datasets, /datasets/:id.
- Reproduksi: assessment tersimpan PASSED tetapi masih memiliki temuan MEDIUM.
- Sesudah: UI memakai Perlu pemeriksaan bila masih ada temuan, Tanpa temuan bila tidak ada; warna status diselaraskan. PASSED tetap mempertahankan semantik penyimpanan lama, yaitu tidak ada HIGH.
- Dashboard melabeli agregat Tanpa temuan prioritas tinggi. Jumlah gagal/diproses dijelaskan agar total tidak disangka penjumlahan dua hasil kualitas saja.
- Bukti: 5 tes frontend pada presentation.test.mjs; status Perlu pemeriksaan/Tanpa temuan terlihat di daftar browser.

### 7. Total Preview salah

- Lokasi: /datasets/52814f91-3fe4-42eb-bdf4-3b6fae820d53.
- Sebelum: badge Preview data 50 karena menghitung sampel tersimpan.
- Sesudah: Preview data 884; pagination 1–25 dari 884 dan halaman 1/36.
- Bukti: accessibility readback dan screenshot desktop. Panel info kosong tidak terlihat.

### 8. Race request

- Lokasi: pencarian /findings, /reference-data, pergantian dataset/preview, pemilihan file /datasets/new.
- Reproduksi konseptual: request A lambat, request B selesai lebih dulu; A kemudian menimpa state B. Pada unggahan, file bisa diganti saat preview file sebelumnya belum selesai.
- Sesudah: nomor request membatasi pembaruan state hanya untuk request terbaru; perubahan file membatalkan penerimaan preview lama. State detail dibersihkan saat ID dataset berubah.
- Bukti: inspeksi guard di kode dan build. Balapan dengan latency buatan belum dites di browser; bukan klaim race-test live.

### 9. Referensi tanpa hasil

- Lokasi: /reference-data.
- Reproduksi: cari ZZZ_TIDAK_ADA_WILAYAH.
- Sesudah: Wilayah tidak ditemukan dengan tombol Hapus pencarian. Klik tombol memulihkan 267 kelurahan dan halaman 1/6.
- Bukti: browser accessibility readback. Jumlah total dilabeli cocok dengan pencarian, bukan seluruhnya ditampilkan pada satu halaman.

### 10. Evidence nilai kosong

- Lokasi: /findings dan preview unggahan.
- Sebelum: null menjadi dash, string kosong terlihat kosong, whitespace tidak terbaca.
- Sesudah: NULL, "", dan simbol whitespace dibedakan; N/A dan 0 tetap tampil apa adanya. Anomali lintas dataset mendapat catatan belum tentu salah, bukan disebut error secara menyeluruh.
- Bukti: tes presentasi frontend; disclosure temuan baris 4 dibuka live dan catatan konfirmasi terlihat.

### 11. Laporan mobile

- Lokasi: detail dataset, viewport 390×667.
- Sebelum: aturan column-reverse membuat PDF/XLSX memenuhi lebar halaman dan label Laporan berada di bawah.
- Sesudah: label dan kedua tombol tersusun dalam satu baris compact; menu mobile punya target 44 px.
- Bukti: screenshot sebelum/sesudah pada browser. Menu mobile dibuka lalu tautan Dataset digunakan, navigasi menutup kembali.

### 12. Fondasi visual tidak konsisten

- Sesudah: halaman utama memakai fondasi navy/white dan Avenir Next/fallback yang sama, heading lebih compact, tabel header terbaca tanpa uppercase dekoratif, sel rata kiri atas. Tidak menambahkan dekorasi atau workflow reviewer.
- Direction: lembar pemeriksaan data dengan controlled density, ENERGY 1 / RHYTHM 1 / MOTION 1. Warna digunakan untuk hierarki dan jenis temuan, bukan mengisi ruang.
- Bukti: build, screenshot dashboard, upload, daftar dataset, detail desktop/mobile. Ini harmonisasi fondasi, bukan klaim setiap komponen/form telah direview di setiap breakpoint.

### 13. Peringatan browser field

- DevTools Issues menampilkan A form field element should have an id or name attribute, berulang sepanjang navigasi/HMR.
- Name ditambahkan pada field pencarian dan filter yang belum memilikinya.
- Sesudah reload detail: 0 page errors, 0 breaking changes, 0 possible improvements; No issues detected di panel Issues.
- Console masih menunjukkan Permissions policy violation: unload is not allowed in this document (repeated 5 times). Tidak ditemukan handler unload/beforeunload/Permissions-Policy dalam frontend/src atau backend/app; sumber belum diatribusi dan tidak dinyatakan sudah diperbaiki.

## Cakupan pengujian

- Baseline: 163 backend tests passed.
- Setelah koreksi: 172 backend tests passed; 5 frontend presentation tests passed; TypeScript/Vite build passed; git diff --check passed.
- Backend Docker lokal direstart; /api/health merespons status ok. Tidak ada deployment remote/produksi.
- Browser: Dashboard, Dataset, Temuan, Referensi, Pengaturan, Assessment baru, Detail/Preview dataset.
- Interaksi: navigasi sidebar; disclosure temuan lintas dataset; pencarian tanpa hasil dan pemulihan di Dataset/Referensi; Preview dengan total/pagination benar; disclosure cakupan assessment lama.
- Mobile 390×667: halaman unggahan, daftar dataset, detail dataset, menu navigasi, dan tombol laporan.
- Screenshot diobservasi lewat sesi browser percakapan; tidak disimpan sebagai file lokal. Tidak ada path screenshot yang dikarang.
- Tidak dites live: login/logout (session pengguna dipertahankan), unggahan baru dengan provider live, download/render laporan PDF/XLSX, race dengan latency buatan, seluruh breakpoint, semua kombinasi error/loading, atau keyboard audit menyeluruh.

## Status terhadap lingkup tesis

IMPLEMENTED: gate pemeriksaan deterministik/statistik; provenance original_value; period formats; log eksekusi baru; ketidakpastian di presentasi; guard confidence semantik.

PARTIALLY IMPLEMENTED: adaptive semantic pipeline (bounded role/candidate analysis tersedia, log per-step belum lengkap); reliabilitas LLM (validasi/fallback/threshold tersedia, retry dan metadata eksperimen belum lengkap); harmonisasi UI (fondasi dan alur inti dicek, bukan exhaustive audit semua state).

MISSING: evaluator ground truth TP/FP/TN/FN, Precision/Recall/F1 dan recommendation accuracy; pengukuran efisiensi inspeksi; metadata kualitas per dimension/version/timing yang lengkap. Tes unit bukan pengganti evaluasi ilmiah.

CONFLICTING WITH THESIS SCOPE / NEEDS POLICY DECISION:

- Uppercase saat ini diberlakukan ke semua nilai teks, sedangkan agents.md membatasinya pada standar organisasi yang berlaku. Memerlukan keputusan pengguna tentang cakupan kolom; belum diubah.
- Kolom tanggal saat ini juga menerima rentang YYYYMMDD S.D. YYYYMMDD, sedangkan aturan tesis menyebut single-date YYYYMMDD. Ekstensi existing dipertahankan sampai keputusan pengguna, bukan diam-diam dihapus.
- Perhitungan yang dipelajari dari mayoritas baris belum setara aturan domain yang diberikan pemilik data. Confidence pola dan bukti tersedia, tetapi kepastian/kebijakan severity perlu diuji dengan ground truth.

Assessment lama tidak dinilai ulang dan tidak diubah. Tidak ada koreksi otomatis nilai sumber, approval states, atau perluasan API Backoffice sebagai inti riset.
