# Tabel baris terdampak

Implemented: tab temuan menampilkan tabel nilai asli, satu baris per nomor sumber, pagination, pencarian konteks sumber, filter ketidaksesuaian/potensi masalah, penanda sel, dan rincian inline.

Keputusan visual: navy membedakan navigasi dan seleksi; merah lembut menandai ketidaksesuaian, amber potensi masalah. Simbol !/? dan label aksesibel mempertahankan makna di luar warna. Angka temuan dan sel ditandai semibold; data lain regular. Header serta nomor sumber sticky untuk orientasi dalam tabel lebar. Scroll horizontal terbatas pada tabel sesuai desain yang diminta, bukan keseluruhan halaman.

Verifikasi:

- Build TypeScript/Vite dan git diff --check lulus.
- 29 tes datasets API lulus, termasuk source-row Excel tidak berurutan dan pencarian CILINCING pada konteks yang tidak memiliki finding sendiri.
- Browser dataset 52814f91-3fe4-42eb-bdf4-3b6fae820d53: 121 baris unik, 239 temuan.
- Filter ketidaksesuaian: satu baris 39, persentase 87.65 ditandai merah.
- Klik sel: membuka satu finding dan rekomendasi 87.5; Tutup rincian bekerja.
- Semua temuan: menampilkan sel anomali amber. Pagination halaman 2 menampilkan posisi 21–40 dari 121.
- Pencarian CILINCING: dua baris, empat findings.
- Klik nomor sumber 154: membuka dua findings pada baris tersebut.
- Lihat baris lengkap: menuju Preview halaman 7; Kembali ke temuan mempertahankan pencarian dan selection serta fokus nomor sumber.
- Tampilan 390 x 667 diperiksa: controls membungkus, tabel scroll di dalam panel, nomor sumber tetap sticky.
- Console sebelum dibersihkan berisi auth/me 401 lama, log unload lingkungan, dan error Vite saat component baru belum selesai dibuat. Build akhir lulus; console setelah dibersihkan menunjukkan 0 messages.

Partially verified: keyboard penuh, failure network, laporan download dan comparison tidak diuji langsung dalam pass ini. Empty/retry ditinjau dari source.

Detektor dan dataset sumber tidak diubah. Cakupan tetap menjelaskan ketiadaan log executed/skipped/failed pada assessment lama.
