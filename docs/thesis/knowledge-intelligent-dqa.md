# Knowledge Tesis Intelligent Data Quality Assessment

Dokumen kerja untuk bahan Bab I–V, berdasarkan kebutuhan pengguna dan inspeksi implementasi proyek pada 13 Oktober 2026. Snapshot kode: commit `489ab3ecd85980a4a62267fab2ab78edf1144fce`. Dokumen ini bukan naskah tesis final dan bukan laporan hasil eksperimen akurasi.

Kesimpulan utama: prototipe telah memiliki pipeline assessment adaptif, pemeriksaan deterministik, referensi administratif, analisis statistik, dan bantuan LLM. Pemilihan pemeriksaan benar-benar memengaruhi eksekusi. Namun, evaluasi ground truth, precision/recall/F1, dan pengukuran penghematan waktu belum tersedia sebagai hasil penelitian.

## 1. Identitas dan posisi penelitian

Judul proyek: **Perancangan Intelligent Data Quality Assessment untuk Otomatisasi Pemeriksaan Kualitas Dataset Statistik Pemerintahan**.

Objek penelitian adalah mekanisme assessment, bukan pembangunan website semata. Aplikasi web menjadi sarana implementasi, demonstrasi, dan evaluasi mekanisme tersebut. Pengguna utama adalah pemeriksa kualitas data atau analis dataset statistik pemerintahan.

Prinsip desain: **Deterministic First, Intelligent When Necessary**. Aturan yang jelas diperiksa dengan metode deterministik; pola numerik diperiksa dengan metode statistik; interpretasi ambigu dibantu LLM. Kata intelligent perlu dijelaskan melalui profiling, pemilihan pemeriksaan yang relevan, dan interpretasi terbatas, bukan sekadar keberadaan API LLM.

Sistem menghasilkan assessment, temuan, bukti, dan rekomendasi. Sistem tidak mengoreksi dataset otomatis, tidak menggantikan analis, serta tidak mencakup workflow persetujuan atau status reviewer. Keputusan koreksi tetap pada pemilik data.

## 2. Bahan Bab I: masalah, tujuan, dan batas penelitian

### Latar belakang yang dapat dikembangkan

Dataset statistik pemerintahan memiliki bentuk kolom dan aturan yang beragam. Pemeriksaan yang relevan untuk tanggal tidak selalu relevan untuk kode wilayah, sedangkan nilai numerik ekstrem tidak selalu salah. Pemeriksaan juga perlu mempertimbangkan hubungan antarkolom dan hierarki referensi, bukan hanya validitas nilai secara terpisah.

Kebutuhan pengguna selama pengembangan menunjukkan masalah penyajian: daftar temuan panjang dan banyak teks menyulitkan pengguna menemukan lokasi masalah. Solusi yang dipilih adalah tabel baris terdampak dengan penandaan sel dan rincian setelah interaksi. Ini merupakan kebutuhan desain dari percakapan pengguna, bukan bukti empiris bahwa waktu atau beban kerja telah berkurang.

### Rumusan masalah usulan

1. Bagaimana merancang mekanisme yang memilih dan menjalankan pemeriksaan sesuai karakteristik dataset?
2. Seberapa baik mekanisme mendeteksi masalah kualitas berdasarkan ground truth per jenis pemeriksaan?
3. Apa kontribusi tambahan bantuan LLM terhadap interpretasi dan rekomendasi dibandingkan pemeriksaan tanpa LLM?
4. Apakah penggunaan prototipe mengubah waktu dan hasil pemeriksaan dibandingkan pemeriksaan manual?

Rumusan ini perlu disepakati dengan pembimbing; bukan keputusan metodologi final.

### Tujuan dan kontribusi yang layak diajukan

Merancang serta mengevaluasi mekanisme yang menggabungkan profiling, seleksi adaptif, validasi deterministik dan referensi, analisis statistik, serta bantuan semantik LLM. Kontribusi potensial terletak pada integrasi dan keterlacakan mekanisme untuk dataset heterogen. Klaim kebaruan perlu ditentukan melalui kajian literatur, bukan diasumsikan dari implementasi.

### Batas penelitian

- Input utama CSV, XLSX, dan XLS; integrasi Backoffice hanya tambahan, bukan pusat eksperimen.
- Referensi administratif saat ini berfokus pada DKI Jakarta, bukan seluruh Indonesia.
- Pemeriksaan dibatasi oleh aturan, karakteristik kolom, dan bukti yang dapat diperoleh sistem.
- Anomali statistik dan dugaan semantik merupakan indikasi untuk diperiksa, bukan kesalahan pasti.
- Akun, pagination, dan penghapusan hasil merupakan fasilitas penggunaan prototipe, bukan kontribusi ilmiah utama.

## 3. Bahan Bab II: kerangka konsep dan kebutuhan literatur

Enam dimensi konseptual dipisahkan meskipun sebagian implementasi berbagi modul:

| Dimensi | Pertanyaan pemeriksaan | Contoh implementasi |
|---|---|---|
| Structural Quality | Apakah struktur dan keterisian data sesuai? | Duplikasi baris, nilai kosong, placeholder |
| Reference Quality | Apakah nilai sesuai master dan hierarki? | Kota, kecamatan, kelurahan |
| Format & Domain Quality | Apakah representasi sesuai aturan yang diketahui? | Uppercase, tanggal, numerik, koordinat |
| Cross-Field / Calculation Quality | Apakah nilai dan hubungan antarkolom konsisten? | Persentase, total, urutan tanggal |
| Statistical Quality | Apakah nilai menyimpang dari distribusi? | Outlier IQR |
| Semantic Quality | Apakah makna atau ejaan mengindikasikan masalah? | Kandidat typo dan interpretasi LLM |

Topik literatur yang harus dicari dari sumber primer: data quality assessment untuk statistik pemerintahan; data profiling dan adaptive validation; reference matching dan hierarchy consistency; outlier IQR; fuzzy matching; LLM-assisted semantic validation; evaluasi precision/recall/F1; serta eksperimen human-in-the-loop dan efisiensi pemeriksaan.

Dokumen ini tidak menyertakan referensi ilmiah yang belum dibaca. Jangan menjadikan aturan uppercase lokal sebagai standar universal, mengatribusikan enam dimensi ini ke suatu standar tanpa verifikasi, atau menyebut metode penelitian tertentu telah dipilih jika belum disepakati.

## 4. Aturan domain dan keputusan pengguna

| Aspek | Aturan atau kebutuhan | Keadaan implementasi |
|---|---|---|
| Missing | `None/NULL`, string kosong, whitespace, dan `-` bermasalah | Pemeriksaan tersedia; literal teks `NULL` berbeda dari nilai null dan tidak otomatis dianggap missing |
| Nilai sah | `N/A`, angka `0`, dan string `0` tidak dianggap missing | Tersedia; jangan menyamakan nilai nol dengan ketiadaan data |
| Tanggal aktual | `YYYYMMDD` dengan validasi kalender | Tersedia |
| Rentang tanggal | Satu sel boleh `YYYYMMDD S.D. YYYYMMDD`, awal tidak melewati akhir | Tersedia dengan pola separator tersebut, bukan semua variasi penulisan rentang |
| Periode statistik | Tahun, bulanan, triwulan, semester | Tersedia untuk `YYYY`, `YYYYMM`, `YYYY-T1`–`T4`, `YYYY-S1`–`S2` |
| Uppercase | Teks mengikuti ketentuan uppercase, kecuali identifier case-sensitive seperti nomor SK/izin `1a.0312Bc` | Uppercase tersedia; pengecualian identifier belum diterapkan |
| Numerik | Pemeriksaan representasi numerik kanonis | Validasi memakai tanda opsional dan titik desimal; jangan mengklaim semua format angka lokal didukung |
| Referensi | Nilai administratif dan hubungan induk-anak harus konsisten | Tersedia menggunakan master DKI |
| Outlier | Nilai ekstrem perlu konfirmasi sumber | Tersedia sebagai potensi anomali |
| Koreksi | Nilai asli tidak ditimpa oleh rekomendasi | Tersedia pada proses assessment |

Kebutuhan uppercase terakhir pengguna adalah pengecualian berdasarkan karakteristik identifier, yang bisa berlaku pada beberapa kolom. Mengabaikan seluruh kolom identifier tanpa aturan juga belum tentu benar. Perlu mekanisme konfigurasi/evidence aturan yang eksplisit agar pengecualian tidak dibuat sembarangan.

## 5. Bahan Bab III: arsitektur dan alur aktual

Alur konseptual:

```text
CSV/Excel → Ingestion → Normalisasi kerja → Profiling
→ Interpretasi karakteristik → Seleksi pemeriksaan relevan
→ Quality Engine → Temuan dan rekomendasi → Laporan
```

Alur aktual unggahan pada snapshot kode:

1. Membaca dan memvalidasi berkas.
2. Menyimpan salinan berkas sumber serta snapshot data kerja.
3. Melakukan profiling awal secara deterministik.
4. Jika LLM dikonfigurasi, menjalankan interpretasi role kolom dan evaluasi kandidat semantik.
5. Menerapkan role yang lolos validasi, memilih pemeriksaan, lalu menjalankan quality engine.
6. Menggabungkan temuan deterministik/statistik dan semantik.
7. Membuat ringkasan tindakan dengan fallback, lalu menyimpan hasil assessment.

Dengan demikian, Deterministic First merupakan prioritas penggunaan metode dan inferensi awal; bukan klaim bahwa setiap pemeriksaan deterministik selesai sebelum panggilan LLM pertama.

### Komponen teknologi

Backend menggunakan Python/FastAPI, SQLAlchemy dan Alembic; PostgreSQL pada konfigurasi Docker. Pembacaan Excel menggunakan openpyxl/xlrd, PDF menggunakan ReportLab, komunikasi LLM menggunakan HTTPX. Frontend menggunakan React, TypeScript, dan Vite. Versi lingkungan eksperimen perlu dicatat dari instalasi/lockfile aktual, bukan hanya deklarasi dependencies.

Assessment dilakukan secara sinkron; belum menggunakan antrean worker. Penyimpanan berkas lokal dan pembacaan snapshot penuh merupakan batas skalabilitas. Pagination API tidak berarti seluruh pipeline telah memproses data secara streaming.

## 6. Ingestion, normalisasi, dan pelestarian sumber

CSV mendukung decoding UTF-8/BOM dengan fallback CP1252 dan deteksi delimiter koma, titik koma, tab, atau pipe. Struktur kolom yang tidak konsisten ditolak. Header duplikat, nama reserved `_source_row`, atau header ambigu juga memiliki validasi.

XLSX/XLS diproses dari worksheet pertama yang berisi data; bukan semua worksheet sekaligus. XLSX membaca hasil formula yang tersimpan jika tersedia dan dapat membawa teks formula apabila cache tidak tersedia. Sistem bukan mesin kalkulasi ulang spreadsheet. Baris kosong dilewati, sedangkan nomor baris sumber dipertahankan.

Normalisasi membuat representasi JSON-safe, termasuk tanggal dan tipe numerik tertentu. Snapshot disimpan sebagai NDJSON terkompresi dengan identitas baris sumber. Berkas asli tidak ditulis ulang menjadi hasil koreksi.

Batas penting: pelestarian salinan sumber berlaku untuk unggahan yang berhasil diproses. Jalur kegagalan dapat membersihkan berkas staging/sumber/snapshot di server. Jangan mengklaim setiap unggahan gagal tetap dapat dipulihkan dari server. Penghapusan hasil dataset saat ini berupa soft delete, bukan penghapusan permanen berkas sumber.

## 7. Profiling dan seleksi adaptif

Profiling menghasilkan jumlah baris/kolom, jumlah duplikasi, tipe inferensi, role kandidat, null/empty/unique count, sampel nilai, dan distribusi frekuensi tertentu. Role meliputi administratif, identifier, tanggal, koordinat, numerik, persentase, kategori, atau teks bebas.

Inferensi tipe tertentu memakai ambang sekitar 90% nilai yang sesuai. Ini heuristik, bukan pemahaman sempurna. Distribusi numerik umum seperti mean/std/quartile tidak seluruhnya disimpan pada profil; quartile IQR dihitung dalam pemeriksaan statistik.

| Pemeriksaan | Syarat relevansi utama |
|---|---|
| Duplikasi, missing, uppercase | Pemeriksaan dasar |
| Referensi administratif | Ada role administratif |
| Tanggal/periode | Ada kolom dengan karakteristik tanggal/periode |
| Koordinat | Ada role latitude/longitude |
| Format numerik | Ada role numerik/persentase yang sesuai |
| Statistik | Kolom numerik dan jumlah baris minimal |
| Kalkulasi | Sedikitnya tiga kolom numerik kandidat |
| Cross-field | Sedikitnya dua kolom tanggal aktual |
| Semantik | Konfigurasi LLM dan kandidat teks yang memenuhi syarat |

Pemeriksaan tersedia, relevan, dan dieksekusi dibedakan dalam metadata. Tes adaptif membuktikan fungsi detektor tidak relevan tidak dipanggil. Log utama mencakup deterministik/statistik; aktivitas semantik belum seluruhnya tercatat dalam daftar eksekusi yang sama. Alasan skip masih bersifat umum.

Risiko untuk diuji: nilai seperti `N/A` atau placeholder dapat memengaruhi denominator inferensi tipe dan menyebabkan role numerik tidak terpilih. Ini risiko yang disimpulkan dari kode, belum hasil pengukuran false negative.

## 8. Mekanisme setiap dimensi

### Structural Quality

Duplikasi baris penuh ditandai setelah kemunculan pertama; unitnya baris, bukan satu sel. Missing meliputi null aktual, string kosong, dan whitespace. Placeholder `-` memiliki temuan tersendiri. Uppercase membandingkan nilai alfabetis dengan representasi uppercase; nilai asli dan rekomendasi tetap terpisah.

### Reference Quality

Pencocokan deterministik memakai nama/kode dalam master dan memeriksa konsistensi kota–kecamatan–kelurahan serta pasangan kode–nama. Nama yang valid tetapi berasal dari kecamatan berbeda tetap bermasalah.

Kandidat nama dapat dibentuk dengan edit distance Levenshtein maksimal dua, penyaringan berdasarkan induk, dan pemilihan kandidat terbaik yang unik. Kandidat ambigu tidak dipaksakan. Confidence kandidat merupakan skor heuristik, bukan probabilitas terkalibrasi.

Master yang diperiksa memuat 267 kelurahan, 44 kecamatan, dan 6 kota/kabupaten. Hash berkas digunakan untuk versi referensi detektor. Jumlah tersebut adalah keadaan master proyek, bukan verifikasi terkini terhadap publikasi resmi pemerintah.

### Format & Domain Quality

Tanggal diperiksa menggunakan pola dan validitas kalender, termasuk rentang yang disepakati. `periode_data` diperlakukan terpisah. Koordinat memeriksa format numerik serta latitude −90 sampai 90 dan longitude −180 sampai 180. Pemeriksaan numerik tidak otomatis menetapkan seluruh aturan bisnis domain.

### Cross-Field / Calculation Quality

Kalkulasi mencari hubungan persentase atau total dari kandidat numerik. Relasi didukung sedikitnya lima baris pembanding dan support minimal 0,8; toleransi utama `max(0.01, abs(expected) × 0.0001)`. Kandidat relasi yang tidak cukup kuat atau ambigu tidak digunakan. Persentase menggunakan pembulatan dua desimal; denominator nol dilewati.

Batas epistemik penting: formula dapat diinferensikan dari pola mayoritas, bukan diperoleh dari aturan bisnis terkonfirmasi. Temuan kalkulasi berseverity HIGH tidak otomatis membuktikan pelanggaran aturan bisnis. Perlu membedakan aturan terkonfirmasi dari hipotesis relasi.

Cross-field tanggal mencari pasangan awal/akhir yang cukup jelas, lalu mendeteksi akhir sebelum awal. Bukan semua hubungan temporal atau semua kombinasi kolom.

### Statistical Quality

Outlier menggunakan IQR dengan sedikitnya delapan nilai numerik valid. Batasnya `Q1 − 1.5 × IQR` dan `Q3 + 1.5 × IQR`; IQR nol tidak menghasilkan penandaan dengan mekanisme ini. Nilai di luar batas ditampilkan sebagai potensi anomali.

Confidence outlier saat ini tetap 0,8. Nilai ini bukan probabilitas nilai salah dan belum dikalibrasi. Nama internal detektor yang mengandung deterministic tidak mengubah kategori konseptualnya menjadi validasi bisnis deterministik.

### Semantic Quality

Kandidat typo dibentuk terlebih dahulu dari nilai dalam kolom menggunakan kemiripan string dan informasi frekuensi, lalu LLM mengevaluasi kandidat yang terbatas. Sistem tidak mengirim seluruh dataset untuk menyerahkan semua keputusan kualitas kepada LLM.

Interpretasi role memakai sampel terbatas dan confidence minimal 0,90. Evaluasi semantik memakai confidence minimal 0,80, alasan nonkosong, tipe keluaran yang diizinkan, dan rekomendasi yang harus cocok dengan kandidat yang didukung. Batas saat ini mencakup hingga 20 kandidat kolom dan 50 kandidat semantik sesuai konfigurasi.

Output JSON divalidasi; respons kosong, JSON rusak, timeout, error API, confidence rendah, dan rekomendasi tidak didukung tidak langsung diterima. Kegagalan LLM tidak menghentikan pemeriksaan deterministik. Temuan parsial yang valid dapat tetap dipertahankan.

Belum terdapat pembuktian efektivitas model/provider aktual pada eksperimen ini. Panggilan kandidat berjalan serial, timeout berlaku per request, dan belum ada retry/backoff atau metadata eksperimen LLM yang lengkap.

## 9. Temuan, rekomendasi, dan interpretasi hasil

Model temuan menyimpan ID, dataset, baris, kolom, issue type, severity, original value, expected value, evidence, recommendation, confidence, detector, serta ringkasan tindakan dan sumber ringkasannya.

Issue type aktual antara lain `DUPLICATE`, `MISSING_VALUE`, `INVALID_PLACEHOLDER`, `INVALID_CASE`, `INVALID_DATE_FORMAT`, `INVALID_REFERENCE`, `INVALID_HIERARCHY`, `INVALID_COORDINATE`, `CALCULATION_MISMATCH`, `CROSS_FIELD_MISMATCH`, `STATISTICAL_ANOMALY`, `POTENTIAL_TYPO`, dan `SEMANTIC_MISMATCH`. Gunakan tipe aktual ketika membangun label evaluasi; daftar contoh dalam pedoman tidak selalu identik dengan enum implementasi.

Belum ada field dimensi kualitas, asal aturan, dan kepastian pelanggaran yang eksplisit untuk seluruh temuan. Pemetaan dimensi dapat disusun untuk analisis, tetapi tidak boleh diklaim sudah lengkap sebagai data tersimpan.

Assessment `PASSED` berarti tidak ada temuan HIGH, bukan jaminan seluruh data benar. Temuan MEDIUM dapat tetap ada. Confidence memiliki arti berbeda antar-detektor: default, support relasi, skor heuristik kandidat, nilai tetap IQR, atau penilaian model. Jangan membandingkannya sebagai probabilitas seragam.

Laporan CSV/XLSX memuat detail terstruktur. XLSX memiliki sheet ringkasan dan temuan. PDF menyajikan ringkasan serta tabel yang lebih terbatas; recommendation, confidence, dan detector tidak seluruhnya menjadi kolom detail PDF. Jangan mengklaim semua format laporan memiliki kelengkapan identik.

## 10. Desain UI sebagai pendukung assessment

Keputusan desain yang disepakati:

- Tampilan utama berupa tabel seluruh baris terdampak, bukan tumpukan kartu teks panjang.
- Sel bermasalah dibedakan menggunakan warna: pelanggaran aturan dan potensi anomali tidak disamakan.
- Penjelasan singkat tersedia ketika hover/fokus; rincian muncul setelah memilih baris atau sel.
- Rincian compact memisahkan nilai asli, rekomendasi, alasan, dan saran pemeriksaan.
- Nama kolom dapat digunakan untuk sorting; nomor baris sumber dan konteks record dipertahankan.
- Detail metode/confidence menggunakan progressive disclosure, termasuk peringatan bahwa skor bukan probabilitas kesalahan.
- Jumlah temuan dibedakan dari jumlah baris terdampak.

Alasan desain: mendahulukan lokasi masalah dan konteks, lalu memberikan analisis saat dibutuhkan. Ini hipotesis desain yang bisa dievaluasi lewat eksperimen pengguna, bukan hasil usability terukur. Ringkasan AI tersedia di backend, tetapi jangan mengklaim seluruh ringkasan tersebut menjadi elemen utama tabel terbaru.

## 11. Fasilitas prototipe di luar kontribusi utama

Akun memiliki role Admin dan Pemeriksa. Hasil baru memiliki pemilik; Pemeriksa mengakses hasil miliknya, sedangkan Admin dapat melihat seluruh hasil. Dataset lama tanpa pemilik hanya tersedia bagi Admin. Pemeriksaan akses berlaku pada endpoint detail, temuan, laporan, dan relasi assessment.

Pembuatan akun menggunakan password awal bersama `Password123`; pengguna dapat mengganti password di profil dengan verifikasi password saat ini. Ini keterbatasan keamanan prototipe dan bukan praktik deployment publik yang dapat dinyatakan aman tanpa kajian tambahan. Jangan memasukkan kredensial nyata atau API key dalam tesis/lampiran.

Daftar dataset memiliki pagination, seleksi bulk, dan swipe untuk membuka konfirmasi penghapusan. Penghapusan adalah soft delete dengan restore yang tunduk pada akses pemilik. Fitur ini mengelola hasil assessment, bukan membersihkan nilai sumber.

Perbandingan assessment menggunakan fingerprint baris, kolom, tipe isu, dan nilai asli untuk membedakan temuan yang tersisa/baru/hilang. Ini bukan evaluator ground truth; perubahan posisi baris atau nilai dapat mengubah fingerprint.

## 12. Audit status terhadap kebutuhan tesis

| Komponen | Status | Catatan |
|---|---|---|
| Pembacaan CSV/XLSX/XLS | IMPLEMENTED | Worksheet pertama berisi data; bukan semua sheet |
| Profiling dan role inference | IMPLEMENTED | Heuristik, tidak sempurna |
| Seleksi adaptif mengontrol eksekusi | IMPLEMENTED | Ada tes detektor tidak relevan tidak dipanggil |
| Pemeriksaan enam dimensi | PARTIALLY IMPLEMENTED | Terdapat mekanisme tiap dimensi; cakupan aturan dan pemetaan data tidak menyeluruh |
| Referensi dan hierarki DKI | IMPLEMENTED | Cakupan master lokal |
| Temuan berbukti dan rekomendasi | IMPLEMENTED | Kelengkapan format laporan berbeda |
| Penanganan kegagalan LLM | IMPLEMENTED | Efektivitas provider langsung belum dibuktikan |
| Confidence yang seragam/terkalibrasi | MISSING | Skor antar-detektor berbeda makna |
| Pengecualian uppercase identifier peka karakter | MISSING | Perilaku sekarang berpotensi berkonflik dengan kebutuhan pengguna |
| Pelestarian sumber pada semua kegagalan upload | PARTIALLY IMPLEMENTED | Cleanup server pada jalur gagal |
| Ground truth dan evaluator TP/FP/TN/FN | MISSING | Fixture tes bukan evaluator penelitian lengkap |
| Precision/recall/F1 hasil eksperimen | MISSING | Tidak ada hasil yang layak diklaim |
| Pengukuran waktu/effort manual vs sistem | MISSING | Belum ada eksperimen |
| Metadata lengkap model/prompt/latensi/token | PARTIALLY IMPLEMENTED | Perlu pencatatan eksperimen |
| Koreksi otomatis dan workflow reviewer | CONFLICTING WITH THESIS SCOPE | Tidak perlu ditambahkan untuk penelitian ini |

## 13. Bahan Bab IV: bukti pengujian yang sudah tersedia

Validasi pada sesi ekstraksi dokumen, terhadap snapshot kode tersebut:

```text
pytest -q backend/tests          → 207 passed (3.58 s)
npm --prefix frontend test       → 10 passed
```

Tes mencakup aturan kualitas, dispatch adaptif, validasi keluaran LLM dengan mock, akses pemilik, pagination, soft delete/restore, dan kontrak frontend terkait presentasi/gesture/API. Fixture API menggunakan database SQLite terisolasi; ini tidak setara dengan uji beban PostgreSQL atau deployment produksi.

Angka 207 dan 10 adalah jumlah tes perangkat lunak yang lolos. Angka tersebut bukan TP, jumlah masalah kualitas yang berhasil ditemukan, akurasi 100%, atau hasil benchmark ilmiah. Tidak dilakukan pengukuran coverage kode, precision, recall, F1, usability, atau provider LLM langsung pada sesi ini.

Artefak dataset uji tersedia di `outputs/phase5-9-test-data/` dan `outputs/01a01250-dummy-quality/`. Nama berkas errors/corrected tidak membuktikan adanya gold standard yang telah divalidasi. Script verifikasi CSV yang tersedia memeriksa hal tertentu pada workbook, bukan confusion matrix deteksi.

Dokumentasi lama perlu diperiksa silang: README memiliki keterangan akses yang tertinggal dibanding implementasi akun, dan script smoke lama belum mengikuti autentikasi/kontrak terbaru. Jangan memakai script lama sebagai bukti tes terkini yang telah lolos.

## 14. Rancangan evaluasi ilmiah yang perlu dilaksanakan

### Ground truth dan injeksi kesalahan

1. Pilih dataset bersih dengan izin penggunaan dan cakupan domain yang terdokumentasi.
2. Verifikasi keadaan bersih bersama pihak yang memahami domain; jangan hanya mengandalkan output sistem sendiri.
3. Simpan sumber baseline, versi master, hash berkas, dan identitas record stabil.
4. Injeksi kesalahan terkontrol per detector, termasuk kasus valid pembanding dan kasus batas.
5. Simpan manifest: ID kasus, ID record, baris sumber, kolom atau cakupan baris, issue type, nilai sebelum/sesudah, expected recommendation, serta alasan label.
6. Jalankan assessment tanpa mengubah sumber, lalu cocokkan hasil dengan manifest menggunakan aturan yang ditetapkan sebelum melihat hasil.

Perlu mencakup nol/N/A sah, periode statistik bukan tanggal, rentang tanggal sah, identifier mixed-case sah, hierarki tidak konsisten, kasus formula ambigu, denominator nol, outlier yang benar secara domain, kandidat typo ambigu, dan kegagalan LLM.

Duplikasi merupakan unit baris; sebagian temuan merupakan unit sel atau pasangan kolom. Tetapkan unit evaluasi per-detektor agar multi-issue pada satu sel tidak dihitung secara keliru. Identitas record stabil diperlukan karena nomor baris dapat bergeser.

### Definisi metrik

- TP: masalah berlabel yang cocok dengan temuan menurut aturan matching.
- FP: temuan yang tidak cocok dengan masalah berlabel dalam ruang evaluasi.
- FN: masalah berlabel yang tidak terdeteksi, termasuk karena seleksi pemeriksaan keliru.
- TN: unit yang layak diperiksa dan berlabel valid, tidak ditandai; hanya dihitung setelah semesta unit didefinisikan.

```text
Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1        = 2 × Precision × Recall / (Precision + Recall)
```

Tetapkan kebijakan denominator nol dan laporkan support. Sajikan hasil per-detektor serta agregasi micro/macro bila sesuai; jangan merata-ratakan jenis masalah berbeda tanpa penjelasan. Accuracy dapat menyesatkan pada dataset dengan banyak unit valid.

Untuk LLM, pisahkan ketepatan deteksi dari ketepatan rekomendasi. Nilai yang tampak mirip belum tentu rekomendasi benar. Untuk outlier, pisahkan anomali statistik terkontrol dari kesalahan data yang benar-benar diketahui.

### Evaluasi seleksi dan ablation

Ukur apakah pemeriksaan yang relevan terpilih dan dieksekusi, bukan hanya jumlah pemeriksaan yang dilewati. FN dapat berasal dari role inference, selection, detector, atau penyajian; telusuri tahap penyebabnya.

Bandingkan konfigurasi yang jelas, misalnya mekanisme tanpa bantuan LLM dan mekanisme dengan bantuan LLM. Jika memakai baseline semua pemeriksaan atau ablation statistik, definisikan runner eksperimen dan guard applicability secara eksplisit; jangan mengklaim konfigurasi pembanding sudah tersedia otomatis di prototipe.

### Evaluasi efisiensi dan pengguna

Bandingkan pemeriksaan manual dengan pemeriksaan berbantuan pada tugas yang sebanding. Catat waktu, masalah benar yang ditemukan, masalah terlewat, dan temuan keliru. Counterbalance urutan tugas atau gunakan dataset setara agar peserta tidak mengingat jawaban dari percobaan pertama.

Catat jumlah peserta, kriteria pengalaman, instruksi, perangkat, ukuran dataset, kondisi jaringan/provider, dan persetujuan partisipasi. Jangan menetapkan jumlah peserta atau signifikansi tanpa rancangan yang dapat dipertanggungjawabkan.

Pisahkan waktu komputasi assessment dari waktu inspeksi manusia. Catat p50/p95 atau ringkasan yang sesuai, pengulangan, kondisi cache, dan error. Latensi satu request bukan latensi seluruh pipeline.

## 15. Peta bahan untuk Bab I–V

| Bab | Bahan dari proyek | Bukti tambahan yang dibutuhkan |
|---|---|---|
| I Pendahuluan | Masalah heterogenitas aturan, kebutuhan analis, tujuan dan batas mekanisme | Bukti konteks organisasi, studi pendahuluan, referensi masalah |
| II Tinjauan pustaka | Kerangka enam dimensi, profiling, selection, deterministic/statistical/LLM | Literatur primer, pembandingan penelitian terdahulu, dasar kebaruan |
| III Metodologi/perancangan | Pipeline, aturan, algoritma, arsitektur, rancangan ground truth | Metode penelitian yang disepakati, prosedur eksperimen dan etika |
| IV Implementasi/hasil | Implementasi aktual, traceability, 207+10 tes software | Hasil eksperimen deteksi, ablation, waktu dan pengguna |
| V Kesimpulan | Kesimpulan sementara tentang realisasi prototipe dan keterbatasan | Kesimpulan efektivitas hanya setelah data Bab IV tersedia |

Design Science Research atau pendekatan pengembangan dan evaluasi artefak dapat dipertimbangkan bersama pembimbing. Kesesuaian metode tidak boleh dinyatakan telah ditetapkan hanya dari keberadaan aplikasi.

## 16. Contoh narasi aman untuk dikembangkan

**Bab I:** Penelitian ini berfokus pada perancangan mekanisme Intelligent Data Quality Assessment untuk membantu pemeriksaan dataset statistik pemerintahan. Mekanisme menggabungkan profiling dan seleksi pemeriksaan yang relevan dengan validasi deterministik, referensi, analisis statistik, serta bantuan semantik terbatas. Aplikasi web digunakan sebagai prototipe untuk menjalankan dan mengevaluasi mekanisme, sedangkan keputusan koreksi tetap berada pada pengguna.

**Bab III:** Karakteristik awal dataset diperoleh melalui profiling. Informasi tersebut digunakan untuk menentukan pemeriksaan yang relevan dan mengendalikan dispatch detektor. Temuan mempertahankan nilai sumber, menyimpan bukti dan rekomendasi, serta membedakan dugaan anomali dari pelanggaran representasi yang memiliki aturan jelas.

**Bab IV—pengujian perangkat lunak:** Pada snapshot implementasi yang diperiksa, 207 tes backend dan 10 tes frontend berhasil dijalankan. Hasil ini memberikan bukti bahwa perilaku yang dicakup tes memenuhi ekspektasi pengujian perangkat lunak. Hasil tersebut belum merupakan evaluasi kinerja deteksi berbasis ground truth maupun bukti efisiensi pemeriksaan manusia.

**Bab V—sementara:** Prototipe telah merealisasikan sejumlah komponen mekanisme assessment adaptif dan penyajian temuan berbukti. Kesimpulan mengenai ketepatan deteksi dan pengurangan waktu pemeriksaan masih memerlukan eksperimen terkontrol. Keterbatasan mencakup inferensi aturan kalkulasi, cakupan referensi, confidence yang belum terkalibrasi, dan pengecualian identifier pada aturan uppercase.

| Klaim yang didukung | Klaim yang belum didukung |
|---|---|
| Seleksi relevansi mengendalikan eksekusi | Semua dataset dapat dipahami dengan benar |
| Nilai asli dan rekomendasi dipisahkan | Sistem mengoreksi otomatis dengan aman |
| Ada penanganan kegagalan LLM yang diuji dengan mock | Provider/model telah terbukti akurat di lapangan |
| Ada IQR untuk potensi anomali | Semua outlier adalah kesalahan data |
| Tes software pada snapshot lolos | Akurasi deteksi 100% atau beban kerja pasti berkurang |
| UI mengutamakan tabel dan rincian sesuai kebutuhan | Usability telah terbukti meningkat secara statistik |

## 17. Prioritas pengembangan untuk penelitian

1. Bangun manifest ground truth dan evaluator matching, dengan unit per-detektor serta pelaporan FP/FN.
2. Terapkan pengecualian uppercase yang berbasis aturan identifier, disertai tes nilai mixed-case yang valid.
3. Pisahkan asal aturan dan kepastian temuan, terutama kalkulasi berbasis pola mayoritas.
4. Lengkapi log selected/executed/skipped dan aktivitas semantik; catat versi konfigurasi, referensi, model/prompt, serta latensi.
5. Siapkan benchmark dan eksperimen manual vs berbantuan tanpa mengklaim hasil sebelum pengukuran.
6. Perbaiki dokumentasi dan script pengujian yang tertinggal agar artefak tesis dapat direproduksi.

Perubahan kosmetik berikutnya sebaiknya hanya dilakukan jika mendukung ketepatan interpretasi, keterlacakan, atau eksperimen penggunaan.

## 18. Peta sumber implementasi

Tautan berikut menunjuk snapshot tetap, bukan branch yang dapat berubah. Gunakan kode sebagai sumber fakta implementasi; gunakan literatur untuk dasar ilmiah.

| Sumber | Isi yang dapat ditelusuri |
|---|---|
| [ingestion.py](https://github.com/RizkyFirman00/Data_Quality/blob/489ab3ecd85980a4a62267fab2ab78edf1144fce/backend/app/ingestion.py) | Pembacaan berkas, header, sheet, nomor baris sumber |
| [profiling.py](https://github.com/RizkyFirman00/Data_Quality/blob/489ab3ecd85980a4a62267fab2ab78edf1144fce/backend/app/profiling.py) | Inferensi tipe/role dan profil |
| [quality.py](https://github.com/RizkyFirman00/Data_Quality/blob/489ab3ecd85980a4a62267fab2ab78edf1144fce/backend/app/quality.py) | Seleksi, dispatch, aturan dan algoritma deteksi |
| [reference.py](https://github.com/RizkyFirman00/Data_Quality/blob/489ab3ecd85980a4a62267fab2ab78edf1144fce/backend/app/reference.py) | Master, hierarki, kandidat referensi |
| [semantic.py](https://github.com/RizkyFirman00/Data_Quality/blob/489ab3ecd85980a4a62267fab2ab78edf1144fce/backend/app/semantic.py) | Kandidat, validasi LLM, fallback ringkasan |
| [models.py](https://github.com/RizkyFirman00/Data_Quality/blob/489ab3ecd85980a4a62267fab2ab78edf1144fce/backend/app/models.py) | Dataset, profil, temuan, akun dan sesi |
| [storage.py](https://github.com/RizkyFirman00/Data_Quality/blob/489ab3ecd85980a4a62267fab2ab78edf1144fce/backend/app/storage.py) | Salinan sumber, snapshot, batas penyimpanan |
| [reports.py](https://github.com/RizkyFirman00/Data_Quality/blob/489ab3ecd85980a4a62267fab2ab78edf1144fce/backend/app/reports.py) | Ekspor dan kelengkapan laporan |
| [backend/tests](https://github.com/RizkyFirman00/Data_Quality/tree/489ab3ecd85980a4a62267fab2ab78edf1144fce/backend/tests) | Bukti perilaku software, bukan hasil benchmark ilmiah |

Keputusan domain dan desain UI dalam dokumen ini juga berasal dari kebutuhan pengguna dalam percakapan pengembangan. Kebutuhan yang belum ada di kode ditandai terpisah; percakapan tidak digunakan sebagai pengganti verifikasi implementasi.

## 19. Checklist sebelum finalisasi tesis

- [ ] Sepakati judul, rumusan masalah, metode, dan batas eksperimen dengan pembimbing.
- [ ] Lengkapi literatur primer dan pembandingan penelitian terdahulu.
- [ ] Pastikan izin penggunaan dataset, anonymization, dan batas pengiriman sampel ke provider LLM.
- [ ] Verifikasi baseline bersih, ground truth, serta aturan matching sebelum menjalankan evaluasi.
- [ ] Catat commit, environment, konfigurasi, versi master, dan kondisi provider tiap eksperimen.
- [ ] Pisahkan hasil software test dari deteksi, efisiensi, usability, dan uji deployment.
- [ ] Laporkan kegagalan serta FP/FN, bukan hanya contoh keberhasilan.
- [ ] Jangan menyamakan confidence dengan probabilitas tanpa kalibrasi.
- [ ] Jangan menyamakan PASSED dengan seluruh dataset pasti benar.
- [ ] Tarik kesimpulan Bab V hanya dari hasil yang benar-benar diukur.
