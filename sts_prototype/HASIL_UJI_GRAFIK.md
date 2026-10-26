# Verifikasi v0.8.0

- 28 pengujian backend API/kalibrasi/riwayat/snapshot/MQTT TCP: lulus.
- TypeScript dan Vite production build: lulus.
- Tes logika grafik: lulus. Nilai null memutus garis, jeda waktu memisahkan bagian grafik, timestamp invalid/duplikat diabaikan, buffer langsung dibatasi, peringkasan 36.000 titik mempertahankan ekstrem, label fase sesuai sumber.
- Tes React DOM/jsdom melalui MQTT.js dan broker aMQTT: lulus. Simulasi FastAPI menghasilkan pesan yang membentuk grafik, hitungan 1/1, sudut dan status selesai. Pemilihan sesi, kalibrasi dan penyembunyian garis diperiksa. Alamat broker diuji mengikuti hostname halaman, sementara soket uji dialihkan ke loopback karena lingkungan tidak memiliki rute jaringan non-loopback.
- Tes React DOM/jsdom untuk riwayat dengan payload asli 699 frame dari sesi pengguna: lulus. Grafik dibuka dari daftar/detail, tiga kurva tampil, null ditampilkan sebagai Tidak tersedia, penunjuk waktu pada 34,43 detik membaca lutut 93,6 derajat sesuai frame sumber, dan kalibrasi bisa ditampilkan. Fetch daftar/detail di tes UI menggunakan respons fixture; persistensi SQLite diuji oleh tes backend.
- Kurva SVG dari sesi 699 frame dirender ke PNG dan diperiksa secara visual untuk sumbu, kurva dan pita fase.

Batas: tidak ada pengujian kamera fisik, HP fisik, atau tampilan browser grafis lengkap di lingkungan Linux ini. Tata letak HP perlu diperiksa pengguna; grafik memakai area geser mendatar agar label tidak terlalu kecil. Tidak ada perubahan basis data, angka aturan STS, atau transport landmark. Riwayat lama ditampilkan tanpa penilaian ulang. Grafik MQTT adalah cuplikan pesan diterima; data seluruh frame tetap pada JSON/SQLite.
