# Intelligent Data Quality Assessment

Phase 4 menyediakan ingest, profiling, pemeriksaan kualitas struktural, validasi referensi administratif DKI Jakarta, serta validasi format tanggal/periode dan numerik untuk reviewer data. Aplikasi menerima CSV/XLSX, mempertahankan file asli, membuat snapshot kerja terpisah, lalu menampilkan preview, karakteristik kolom, evidence, dan rekomendasi.

Aplikasi tidak mengubah dataset sumber dan belum memberikan verdict lulus/gagal. Reviewer tetap menjadi pengambil keputusan.

## Pemeriksaan Phase 2–4

- Duplikat hanya untuk baris lengkap yang sama; kemunculan pertama menjadi referensi.
- `NULL`, string kosong, dan whitespace-only adalah `MISSING_VALUE`.
- String `-` adalah `INVALID_PLACEHOLDER`.
- Semua nilai string yang mengandung huruf harus uppercase; rekomendasi tidak diterapkan otomatis.
- `N/A`, angka `0`, dan string `"0"` tetap valid dan bukan missing.
- Kolom administratif yang dikenali secara eksplisit divalidasi terhadap `backend/reference/master.csv`: 267 kelurahan, 44 kecamatan, dan 6 kota/kabupaten.
- Header `wilayah` dipetakan khusus ke kota/kabupaten. Nama dibandingkan secara uppercase tanpa mengubah nilai sumber; kode dibandingkan sebagai string persis.
- Hubungan kota/kabupaten–kecamatan–kelurahan divalidasi hanya setelah masing-masing nilai valid, sehingga temuan tidak berantai dari referensi yang salah.
- Master yang hilang atau rusak membuat health dan upload gagal secara aman; layanan tidak menjalankan pemeriksaan dengan referensi yang tidak tepercaya.
- Kolom tanggal dipilih dari profil atau hint eksplisit: bentuk `tanggal`/`tgl`, `date`, `birthdate`, `startdate`, `enddate`, dan `eventdate`. Kata umum seperti `candidate`, `validate`, `mandate`, dan `update` tidak dianggap hint tanggal.
- Tanggal aktual hanya valid dalam format `YYYYMMDD`, atau rentang persis `YYYYMMDD S.D. YYYYMMDD`. Kedua tanggal harus valid dalam kalender Gregorian dan tanggal awal tidak boleh melewati tanggal akhir.
- Header `periode_data` menerima hanya `YYYY` atau `YYYYMM`; bulan harus `01`–`12` dan periode tidak menerima rentang.
- Semua digit format tanggal/periode wajib digit ASCII `0`–`9`. Digit Arab-Indic dan fullwidth ditolak.
- Sel XLSX whole-number dapat memenuhi format digit. Boolean, float, serta sel native date/datetime tetap menghasilkan temuan; native date/datetime mendapat rekomendasi `YYYYMMDD` yang JSON-safe.
- Nilai missing, whitespace-only, `-`, dan `N/A` dilewati oleh pemeriksaan tanggal agar tidak menduplikasi temuan struktural.
- Hanya kolom dengan minimal 90% evidence numerik pada profil yang diperiksa sebagai numerik; nama header tidak dipakai untuk menebak artinya.
- Format numerik kanonis memakai digit ASCII, tanda opsional, dan titik desimal: `0`, `-12`, `+0.5`, dan `1.000` valid. Titik selalu berarti desimal; seribu ditulis `1000`.
- Koma desimal/ribuan, scientific notation, simbol mata uang, boolean, `NaN`, infinity, serta digit Unicode menghasilkan `FORMAT_ERROR`. Nilai XLSX bertipe Number tetap valid.

## Menjalankan lokal

Prasyarat: Docker Desktop dan Docker Compose.

```bash
cp .env.example .env
```

Ubah `POSTGRES_PASSWORD` dan bagian password dalam `DATABASE_URL` dengan nilai yang sama. Untuk evaluasi lokal cepat, default pada `compose.yaml` tetap dapat dipakai tanpa `.env`.

```bash
docker compose up --build -d
docker compose ps
```

Buka:

- UI: <http://localhost:5173>
- API docs: <http://localhost:8000/docs>
- Health: <http://localhost:8000/api/health>

Hentikan layanan tanpa menghapus data:

```bash
docker compose down
```

## Pengujian

Backend:

```bash
docker compose exec backend pytest -q
```

Frontend:

```bash
docker compose exec frontend npm run typecheck
docker compose exec frontend npm run build
```

Smoke test dengan CSV dan XLSX contoh:

```bash
docker compose exec backend env SAMPLES_DIR=/samples python scripts/smoke_test.py
```

`backend/scripts/create_samples.py` tersedia untuk meregenerasi file XLSX sampel dari CSV pada environment Python yang sudah memasang dependensi backend. Berikan path CSV sebagai argumen untuk meregenerasi satu sampel saja.

## Konfigurasi

| Variabel | Default lokal | Keterangan |
|---|---:|---|
| `DATABASE_URL` | koneksi PostgreSQL Compose | Hanya backend |
| `STORAGE_ROOT` | `/data/storage` | Lokasi file asli dan snapshot |
| `MASTER_REFERENCE_PATH` | `/app/reference/master.csv` | Snapshot referensi administratif backend |
| `MAX_UPLOAD_MB` | `25` | Batas upload server-side |
| `MAX_DATASET_ROWS` | `100000` | Batas baris data per dataset |
| `MAX_DATASET_COLUMNS` | `1000` | Batas kolom per dataset |
| `MAX_DATASET_CELLS` | `2000000` | Batas gabungan sel untuk mencegah amplifikasi memori |
| `MAX_FINDINGS` | `10000` | Batas temuan kualitas; dataset ditolak jika terlampaui |
| `PREVIEW_ROWS` | `50` | Batas record yang dikirim ke browser |
| `CORS_ORIGINS` | `http://localhost:5173` | Origin frontend yang diizinkan |
| `VITE_API_URL` | `http://localhost:8000/api` | Base URL API publik |

File pengguna disimpan di `storage/originals/` dengan nama UUID. Snapshot kerja berada di `storage/snapshots/`. Nama file pengguna tidak pernah dipakai sebagai path penyimpanan.

## Batas Phase 4

- Format resmi: CSV dan XLSX; XLS lama belum didukung.
- Pemrosesan masih sinkron karena target awal kecil. Queue ditambahkan hanya bila pengukuran menunjukkan kebutuhan.
- Penyimpanan lokal cocok untuk satu host. Object storage diperlukan sebelum menjalankan banyak instance.
- Belum ada autentikasi; gunakan hanya dalam lingkungan lokal/internal terkontrol.
- Belum ada fuzzy matching/typo, LLM, koordinat, kalkulasi, statistik, keputusan reviewer, filter findings, atau export laporan. Klasifikasi koordinat dan cross-field ditunda ke Fase 6 agar menggunakan pemahaman semantik LLM, bukan alias header yang rapuh.
- Pemeriksaan tanggal hanya mencakup format aktual dan `periode_data` di atas; belum ada metadata jadwal atau inferensi semantik tanggal lain.
- Findings Phase 2–4 bersifat read-only dan harus diverifikasi reviewer.
