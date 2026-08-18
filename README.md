# Intelligent Data Quality Assessment

Phase 1 adalah fondasi ingest dan profiling dataset untuk reviewer data Pemerintah Provinsi DKI Jakarta. Aplikasi menerima CSV/XLSX, mempertahankan file asli, membuat snapshot kerja terpisah, lalu menampilkan preview dan karakteristik kolom.

Phase 1 belum memberikan verdict kualitas, findings, rekomendasi, validasi referensi DKI, atau koreksi data.

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

`backend/scripts/create_samples.py` tersedia untuk meregenerasi `sample_profiling.xlsx` dari CSV pada environment Python yang sudah memasang dependensi backend.

## Konfigurasi

| Variabel | Default lokal | Keterangan |
|---|---:|---|
| `DATABASE_URL` | koneksi PostgreSQL Compose | Hanya backend |
| `STORAGE_ROOT` | `/data/storage` | Lokasi file asli dan snapshot |
| `MAX_UPLOAD_MB` | `25` | Batas upload server-side |
| `MAX_DATASET_ROWS` | `100000` | Batas baris data per dataset |
| `MAX_DATASET_COLUMNS` | `1000` | Batas kolom per dataset |
| `MAX_DATASET_CELLS` | `2000000` | Batas gabungan sel untuk mencegah amplifikasi memori |
| `PREVIEW_ROWS` | `50` | Batas record yang dikirim ke browser |
| `CORS_ORIGINS` | `http://localhost:5173` | Origin frontend yang diizinkan |
| `VITE_API_URL` | `http://localhost:8000/api` | Base URL API publik |

File pengguna disimpan di `storage/originals/` dengan nama UUID. Snapshot kerja berada di `storage/snapshots/`. Nama file pengguna tidak pernah dipakai sebagai path penyimpanan.

## Batas Phase 1

- Format resmi: CSV dan XLSX; XLS lama belum didukung.
- Pemrosesan masih sinkron karena target awal kecil. Queue ditambahkan hanya bila pengukuran menunjukkan kebutuhan.
- Penyimpanan lokal cocok untuk satu host. Object storage diperlukan sebelum menjalankan banyak instance.
- Belum ada autentikasi; gunakan hanya dalam lingkungan lokal/internal terkontrol.
- `N/A` dan `0` dipertahankan sebagai nilai. Profiling bukan quality finding.
