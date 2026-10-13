# Pembuatan akun sederhana

Implemented: Pengaturan menampilkan form nama, username, dan role Admin/Pemeriksa bagi Admin, plus daftar akun aman. Pemeriksa tidak melihat pengelolaan akun dan API menolak aksesnya. Role memakai LocalUser.is_admin existing, tanpa migration atau reviewer workflow.

Direction: lembar pengaturan compact untuk administrator, ENERGY 1 / RHYTHM 1 / MOTION 1. Form berada di atas daftar agar daftar pendek tidak menyisakan setengah panel kosong. Tiga input sejajar pada desktop dan bertumpuk pada mobile. Warna dan typography mengikuti halaman assessment yang disetujui pengguna.

## Keamanan dan batas

- Password awal Password123 ditentukan server, disimpan sebagai hash, tidak dikembalikan oleh API.
- Pengecualian password awal berlaku hanya pada jalur provisioning dengan nilai persis yang diminta. Password normal dan perubahan password tetap mensyaratkan 12–128 karakter.
- Require-user dan CSRF existing tetap dipakai; require-admin melindungi GET/POST /api/users.
- Payload menolak role asing dan field tambahan seperti password/is_admin. Username dinormalisasi dan duplikat ditolak, termasuk race constraint dengan rollback.
- Password bersama ini hanya cocok sebagai awal pada prototipe lokal. Belum ada UI ubah password atau kewajiban ubah password saat login pertama; administrator dapat memakai CLI existing. Akun existing tidak diubah.

## Evidence

- Backend suite PASS: 184 tests. Tes akun/auth terarah: 18 passed, mencakup dua role, hash password awal, login, akses Pemeriksa, auth/CSRF, duplikat, input invalid, dan respons tanpa hash/password.
- Frontend baseline presentation tests PASS: 5 tests; bukan tes komponen form akun.
- Build PASS: TypeScript/Vite.
- Patch hygiene PASS: git diff --check.
- Browser appearance PASS: desktop dan viewport 390×667 diperiksa.
- Browser validation PASS: submit form kosong memfokuskan nama dan menampilkan validasi required; tidak membuat akun.
- Browser role selector PASS: pilih Admin mengubah teks hak akses; dikembalikan ke Pemeriksa.
- Browser account list PASS: daftar dari API tampil, termasuk label Anda pada akun aktif.
- Console: tidak terlihat error baru dari fitur akun; warning Permissions policy violation: unload tetap terlihat dari sesi sebelumnya, sehingga tidak diklaim console sepenuhnya bersih.
- Backend lokal direstart dan health status ok. Tidak membuat akun tambahan di database aktif, tidak mengubah password existing, dan tidak melakukan push otomatis.

Creation success/error UI diperiksa melalui wiring dan tes API, bukan pengiriman form valid live. Semua kombinasi mobile/keyboard/loading/error belum diuji exhaustively.
