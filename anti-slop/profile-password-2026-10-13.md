# Profil dan penyempurnaan layout akun

IMPLEMENTED: pengguna Admin dan Pemeriksa dapat mengganti password sendiri melalui /profile. Pengelolaan akun tetap khusus Admin. Tidak ada workflow pemeriksaan baru, perubahan sumber dataset, atau perubahan password akun existing secara otomatis.

Direction dari desain assessment yang disetujui pengguna: lembar kerja ringkas, navy dan putih, Avenir Next, ENERGY 1 / RHYTHM 1 / MOTION 1. Persetujuan perubahan: pengguna meminta memperbaiki layout akun dan melanjutkan fitur Profil.

## Keputusan desain

- Lebar halaman dibatasi agar tiga input tidak menyebar ke seluruh layar besar.
- Judul bold, label semibold, keterangan regular untuk membedakan tugas utama dari penjelasan.
- Form berlatar sangat ringan memisahkan input dari daftar akun tanpa menambah kartu bertumpuk.
- Catatan password awal dipadatkan, bukan kotak besar; tombol sejajar di kanan pada desktop.
- Daftar akun menggunakan tabel untuk membandingkan nama, username, dan akses.
- Pada mobile, username berada di bawah nama agar tidak terpotong menjadi potongan pendek.
- Profil memisahkan identitas readonly dan form password; tidak menambahkan foto, statistik, atau dekorasi.
- Akses Profil tersedia melalui nama akun desktop dan label Profil mobile, dengan target 44 px.
- Role memakai warna navy/netral untuk informasi akses, bukan status approval.

## Keamanan

- Password saat ini diverifikasi terhadap hash milik pengguna yang sedang login, bukan username dari payload.
- Password baru 12–128 karakter, harus berbeda dan cocok dengan konfirmasi.
- CSRF dan autentikasi existing tetap berlaku. Field tambahan ditolak.
- SecretStr menyamarkan representasi model. Respons validasi endpoint tidak memantulkan input password.
- Kesalahan verifikasi mengikuti batas percobaan dan penguncian existing.
- Perubahan sukses mencabut semua sesi akun itu, menghapus cookie, dan menampilkan pesan login kembali.
- Penggantian saat login pertama bersifat opsional sesuai permintaan "bisa", bukan kewajiban baru.
- Bug logout membaca respons 204 sebagai JSON diperbaiki dengan penanganan respons kosong.

## Bukti verifikasi

- Backend PASS: 196 tests, termasuk 12 tes perubahan password dengan SQLite terpisah, dua role, password salah, lockout, konfirmasi, same-password, panjang, payload tambahan, auth/CSRF, pencabutan dua sesi, dan login menggunakan password baru.
- Frontend PASS: build TypeScript/Vite; 6 tests, termasuk regresi logout respons kosong. Tes frontend bukan pengujian komponen menyeluruh.
- Browser PASS: nama akun menuju /profile; profil Admin dan Pemeriksa terlihat dengan identitas masing-masing; submit form password kosong memfokuskan password saat ini dengan validasi required.
- Browser PASS: Pengaturan Pemeriksa tidak menampilkan pengelolaan akun; setelah user login Admin, form dan dua akun actual tampil. Submit akun kosong tertahan required, tidak membuat akun.
- Browser PASS: pilihan Admin mengubah keterangan akses dan dikembalikan ke Pemeriksa.
- Browser PASS: desktop dan 390×667 diperiksa untuk Profil, form akun, dan tabel. Pada mobile username tampil utuh di bawah nama; form dan tombol tersusun satu kolom.
- Keyboard PASS: dari field konfirmasi, Escape menutup autofill dan Tab memfokuskan Simpan password dengan outline terlihat. Urutan form akun mengikuti nama, username, role, submit melalui struktur DOM.
- Console: warning unload dari host instrumentation masih ada. Error logout lama ditemukan saat user berpindah akun; patch respons 204 lulus tes regresi. Logout live tidak diulang agar sesi Admin milik pengguna tetap dipertahankan.
- Backend aktif direstart, /api/health mengembalikan status ok.
- Tidak membuat akun tambahan atau mengubah password di database aktif. Submit perubahan password sukses diuji pada DB terpisah, bukan melalui UI pengguna.

## Delivery gate

Hard Gate PASS untuk lingkup perubahan: route nyata, label/validasi form, state loading/error/success tersedia, tidak ada konten rekaan atau asset baru, kontrol minimal 44 px; desktop/mobile dan fokus diperiksa. Warna teks ink #203b52 dan muted #546779 pada putih/light wash dipertahankan dari desain existing. Batas: error/loading/success browser tidak diuji menyeluruh, hasil API diuji otomatis; perubahan kredensial live sengaja tidak dijalankan.

Purpose Gate PASS: palette, typography, pemisah, role labels dan batas lebar memiliki alasan di atas; tidak ada gradient, glow, foto, ilustrasi, atau motion dekoratif baru.

Liveliness PASS: dials 1/1/1; focal point form dan tombol tugas, hierarki bobot tulisan, motif lembar assessment navy, whitespace sebagai pemisah bukan panel kosong.

Craftsmanship PASS: memakai modul auth existing dan dua role yang diminta, layout berbasis form/daftar nyata, tidak menambah scope penelitian; build dan tes dijalankan. Tidak melakukan push otomatis.

## Penyesuaian posisi Profil

Mengikuti klarifikasi pengguna, akses Profil dipindah ke kiri top bar, bukan sidebar. Ikon people memakai stroke dan ukuran sekelas ikon existing untuk menandai akses akun. Tombol Keluar tetap di kanan. Nama panjang memakai ellipsis agar tidak mendesak tombol, tanpa mengubah identitas di halaman Profil. Build dan enam tes frontend PASS; klik akses kiri top bar berhasil membuka /profile dan posisi ikon diperiksa pada screenshot desktop. Sidebar tidak memiliki menu Profil tambahan. Pemeriksaan mobile sebelumnya tidak dianggap sebagai verifikasi posisi top bar yang baru.
