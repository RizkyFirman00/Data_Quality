# Intelligent Data Quality Assessment

Platform ini melengkapi ingest, profiling, pemeriksaan kualitas deterministik dan semantik terbatas, statistik, report, Backoffice API, dan reassessment. Aplikasi menerima CSV/XLSX/XLS atau Backoffice API, mempertahankan file asli, membuat snapshot kerja terpisah, lalu menampilkan evidence dan rekomendasi tanpa mengubah sumber data.

Aplikasi memberi status assessment berdasarkan temuan severity tinggi, tetapi tidak mengubah dataset sumber. Temuan ditampilkan sebagai evidence read-only untuk diperiksa pengguna.

## Pemeriksaan Phase 2–4

- Duplikat hanya untuk baris lengkap yang sama; kemunculan pertama menjadi referensi.
- `NULL`, string kosong, dan whitespace-only adalah `MISSING_VALUE`; nilai yang direkomendasikan adalah `N/A`.
- String `-` adalah `INVALID_PLACEHOLDER`.
- Semua nilai string yang mengandung huruf harus uppercase; pelanggaran menjadi temuan severity tinggi dan rekomendasi tidak diterapkan otomatis.
- `N/A`, angka `0`, dan string `"0"` tetap valid dan bukan missing.
- Kolom administratif yang dikenali secara eksplisit divalidasi terhadap `backend/reference/master.csv`: 267 kelurahan, 44 kecamatan, dan 6 kota/kabupaten.
- Header `wilayah` dipetakan khusus ke kota/kabupaten. Nama dibandingkan secara uppercase tanpa mengubah nilai sumber; kode dibandingkan sebagai string persis.
- Hubungan kota/kabupaten–kecamatan–kelurahan divalidasi hanya setelah masing-masing nilai valid, sehingga temuan tidak berantai dari referensi yang salah.
- Master yang hilang atau rusak membuat health dan upload gagal secara aman; layanan tidak menjalankan pemeriksaan dengan referensi yang tidak tepercaya.
- Kolom tanggal dipilih dari profil atau hint eksplisit: bentuk `tanggal`/`tgl`, `date`, `birthdate`, `startdate`, `enddate`, dan `eventdate`. Kata umum seperti `candidate`, `validate`, `mandate`, dan `update` tidak dianggap hint tanggal.
- Tanggal aktual hanya valid dalam format `YYYYMMDD`, atau rentang persis `YYYYMMDD S.D. YYYYMMDD`. Kedua tanggal harus valid dalam kalender Gregorian dan tanggal awal tidak boleh melewati tanggal akhir.
- Header `periode_data` menerima `YYYY`, `YYYYMM`, `YYYY-T1` sampai `YYYY-T4`, dan `YYYY-S1` sampai `YYYY-S2`; bulan harus `01`–`12` dan periode tidak menerima rentang.
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

Buat akun lokal pertama. Password diminta secara interaktif dan tidak disimpan di shell history:

```bash
docker compose exec backend python scripts/manage_user.py create \
  --username admin --display-name "Administrator" --admin
```

Perintah lain yang tersedia adalah `password`, `enable`, dan `disable`. Mengubah password atau menonaktifkan akun mencabut seluruh session aktif.

Admin dapat membuat akun melalui **Pengaturan → Akun pengguna** dengan nama, username, dan role `Admin` atau `Pemeriksa`. Pemeriksa dapat menggunakan assessment tetapi tidak dapat membuat atau melihat daftar akun melalui API pengelolaan akun. Role ini bukan status reviewer atau approval temuan.

Password awal akun yang dibuat melalui UI adalah `Password123`, sesuai kebutuhan prototipe, dan tetap disimpan sebagai hash. Pengecualian password awal tidak menurunkan kebijakan password biasa (12–128 karakter). Setelah login, Admin maupun Pemeriksa dapat membuka Profil melalui ikon people dan nama akun di kiri top bar, lalu mengganti password dengan memasukkan password saat ini, password baru, dan konfirmasinya. Perubahan berhasil mencabut semua sesi akun tersebut dan meminta login kembali. Perubahan tidak diwajibkan saat login pertama, tetapi password awal bersama tidak layak untuk deployment publik. Administrator tetap dapat memakai `python scripts/manage_user.py password --username <username>` untuk reset. Akun existing tidak berubah hanya karena fitur ditambahkan.

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
docker compose exec frontend npm test
```

Tes presentasi frontend memakai Node.js 22 atau lebih baru. Label `Tanpa temuan` berarti tidak ada temuan dari pemeriksaan yang dilakukan, bukan jaminan seluruh nilai benar. Status tersimpan `PASSED` tetap berarti tidak ada temuan severity tinggi; jika masih ada temuan lain, UI menampilkan `Perlu pemeriksaan`.

Assessment baru memilih detektor deterministik/statistik dari profil yang efektif dan menyimpan daftar `available`, `relevant`, `executed`, serta `skipped` beserta alasannya dalam `source_metadata.quality_checks`. Assessment lama tidak diubah atau diberi log retroaktif. Rencana di preview bersifat awal dan dapat berubah setelah peran kolom diperjelas. LLM tetap terpisah; kegagalannya tidak membatalkan hasil deterministik. Confidence temuan semantik minimum adalah 0.8 sebagai kebijakan operasional awal, bukan threshold yang sudah divalidasi melalui ground truth.

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
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | kosong | Endpoint OpenAI-compatible server-side untuk rekomendasi typo |
| `LLM_MAX_COLUMNS` | `20` | Maksimal profil kolom ambigu dalam satu klasifikasi role |
| `LLM_MAX_CANDIDATES` | `50` | Maksimal kandidat typo free-text per assessment |
| `LLM_MAX_ACTION_GROUPS` | `20` | Maksimal kelompok baris dan kategori yang dirangkum AI per assessment |
| `LLM_TIMEOUT_SECONDS` | `10` | Batas panggilan LLM |
| `AUTH_COOKIE_NAME` | `dq_session` | Nama cookie session lokal |
| `AUTH_COOKIE_SECURE` | `false` | Set `true` ketika aplikasi dilayani melalui HTTPS |
| `AUTH_SESSION_HOURS` | `8` | Masa berlaku session server-side |
| `AUTH_MAX_FAILED_ATTEMPTS` | `5` | Batas kegagalan sebelum akun dikunci sementara |
| `AUTH_LOCK_MINUTES` | `15` | Durasi penguncian akun |
| `BACKOFFICE_API_BASE_URL` | kosong | Endpoint Backoffice DataTables-style server-side |
| `BACKOFFICE_API_TOKEN` | kosong | Bearer token Backoffice, tidak pernah dikirim ke browser |
| `BACKOFFICE_PAGE_SIZE` | `100` | Ukuran halaman Backoffice |
| `BACKOFFICE_TIMEOUT_SECONDS` | `10` | Batas panggilan Backoffice |

File pengguna disimpan di `storage/originals/` dengan nama UUID. Snapshot kerja berada di `storage/snapshots/`. Nama file pengguna tidak pernah dipakai sebagai path penyimpanan.

## Workflow pemeriksaan dan batas layanan eksternal

- Dashboard menunjukkan ringkasan assessment dan temuan dari assessment terakhir.
- Temuan dapat dicari/difilter dan ditampilkan read-only sebagai evidence pemeriksaan. Tidak ada status approval, reviewer tercatat, atau endpoint perubahan status temuan.
- Halaman global menyediakan temuan lintas dataset, master referensi wilayah, dan capability server yang aman ditampilkan.
- Report lengkap tersedia sebagai CSV, XLSX dua-sheet, dan PDF. Reassessment dapat dihubungkan ke assessment sebelumnya lalu dibandingkan sebagai resolved, remaining, atau new.
- Outlier IQR adalah `STATISTICAL_ANOMALY` (evidence medium), bukan klaim data pasti salah.
- Koordinat lintang/bujur diperiksa secara deterministik terhadap format angka kanonis dan rentang bumi.
- Perhitungan persentase dan total dua komponen hanya diperiksa jika minimal lima baris membentuk pola konsisten; urutan pasangan tanggal mulai–selesai diperiksa jika pasangannya tidak ambigu.
- LLM menerima profil ringkas kolom ambigu dalam satu batch untuk klasifikasi role berkeyakinan minimal 0,90. Setelah itu LLM hanya menerima kandidat typo free-text pendek non-wilayah/non-alamat yang sudah difilter dari nilai dalam kolom yang sama. Jika tidak dikonfigurasi atau gagal, assessment tetap selesai dengan pemeriksaan deterministik.
- Preview unggahan membaca maksimal 10 contoh baris, profil kolom, dan rencana pemeriksaan tanpa menyimpan assessment atau memanggil LLM.
- Integrasi Backoffice bersifat opsional untuk mengambil dataset langsung melalui endpoint dan token server-side; aplikasi tidak terhubung ke API login Backoffice Satu Data Jakarta. Jika belum dikonfigurasi, tombolnya menampilkan error aman.
- Seluruh UI dan API selain health memerlukan akun lokal. Password memakai Argon2; session dapat dicabut, cookie bersifat `HttpOnly`/`SameSite=Lax`, dan request perubahan memerlukan token CSRF.

## Batas yang tetap disengaja

- Format unggahan: CSV, XLSX, dan XLS BIFF lama. Nilai formula XLS mengikuti cached result yang tersimpan di workbook.
- Pemrosesan masih sinkron karena target awal kecil. Queue ditambahkan hanya bila pengukuran menunjukkan kebutuhan.
- Penyimpanan lokal cocok untuk satu host. Object storage diperlukan sebelum menjalankan banyak instance.
- Relasi kalkulasi domain lain tidak ditebak. Tambahkan hanya setelah ada pola data yang kuat atau metadata aturan bisnis yang nyata.
- Tidak ada Redis/worker. Pemrosesan tetap sinkron dalam batas baris/kolom/sel yang dikonfigurasi.
- Autentikasi lokal saat ini memiliki satu tingkat akses aplikasi; flag admin disimpan untuk administrasi akun tetapi belum menjadi role izin terpisah. Gunakan HTTPS dan `AUTH_COOKIE_SECURE=true` sebelum exposure di luar host lokal.
- Pemeriksaan tanggal hanya mencakup format aktual dan `periode_data` di atas; belum ada metadata jadwal atau inferensi semantik tanggal lain.
- Findings Phase 2–4 bersifat read-only dan perlu diverifikasi pengguna.
