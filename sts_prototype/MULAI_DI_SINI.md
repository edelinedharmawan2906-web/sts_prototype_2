# Unduhan lengkap lebih cepat — v06

Paket ini melanjutkan riwayat ringan v05. Memuat Lambda v08 + pembaruan frontend.

## Tiga perubahan
1. Sekali permintaan mengambil lebih banyak batch hingga batas respons aman,
   menggantikan batas tetap 3 batch. Landmark tetap lengkap.
2. Browser membagi versi sesi menjadi hingga 3 rentang terpisah. Ketiga rentang
   dapat diambil bersamaan, lalu digabungkan kembali sesuai urutan aslinya.
3. Progres tampil: Mengunduh X dari Y batch. Setelah seluruh batch masuk, label
   Menyiapkan file tampil sebelum browser menyimpan JSON.

Berlaku pada Unduh JSON lengkap di riwayat, pengambilan data setelah Akhiri &
simpan, dan Unduh sesi cloud terakhir. Jika data sesi aktif sudah tersedia di
browser, tombol unduh memakai data yang sudah diambil tanpa permintaan baru.

## Cara memasang
1. Ekstrak ISI ZIP ini ke folder proyek berisi api.py dan .venv-api, biasanya
   D:\sts_prototype\sts_prototype. Gabungkan/timpa camera_cloud_payload lama.
   install_camera_cloud.py dan camera_cloud_payload harus sejajar dengan api.py.
2. AWS Console → Lambda → sts-api → Code → Update → .zip file.
   Upload STS_Lambda_v08.zip DI DALAM paket ini. Klik Save dan tunggu update selesai.
   Jangan ekstrak ZIP Lambda dan jangan upload ZIP paket luar.
3. Buka PowerShell di folder proyek, jalankan:

   .\.venv-api\Scripts\python.exe install_camera_cloud.py

4. Biarkan backend berjalan. Jika belum, di terminal PowerShell lain jalankan:

   .\.venv-api\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000

5. Buka http://localhost:8000/camera/?backend=cloud lalu Ctrl+F5.
   Login AWS jika diperlukan; setelah login buka kembali URL mode cloud di atas.
6. Pilih sesi lama di Riwayat latihan cloud, tunggu grafik lengkap, kemudian klik
   Unduh JSON lengkap sesi ini. Perhatikan progres batch dan waktu unduh.
   Tidak perlu mengulang latihan/kalibrasi atau membuat sesi baru.

## Kelengkapan dan kompatibilitas
Format ekspor camera-cloud-v02 tetap sama: hasil, kalibrasi, batches dan frames
lengkap termasuk landmark. Mesin penilaian, aturan, timestamp dan hitungan tetap.
Sesi terbuka menggunakan satu snapshot versi saat pengambilan dimulai. Data yang
masuk sesudah itu tidak dicampur ke ekspor. Sesi lama tetap dapat dibaca.
Browser memeriksa ID sesi, batas versi, urutan tanpa celah/duplikat, cursor maju
serta jumlah akhir batch. File JSON hanya dibuat setelah semua bagian berhasil.
Jika ada kegagalan, pesan error tampil; klik unduh ulang. Respons jaringan yang
hilang dicoba ulang dengan permintaan yang sama tanpa menambah data sesi.
Unduhan ulang yang dimulai pengguna mengambil snapshot baru jika sesi berjalan.
Progres menghitung batch, bukan byte/detik; loncat beberapa batch adalah normal.

## Teknis dan AWS
Action baru export_history pada POST /sts; history lama dan angles tetap ada.
Satu request membaca paling banyak satu halaman DynamoDB (batas query 1 MiB,
Limit maksimum 100), dengan tambahan batas JSON respons 900 KiB. Cursor berhenti
pada batch terakhir yang dikirim, sehingga sisa halaman tidak hilang ketika
batas respons tercapai. Rentang versi dipisahkan sebelum request paralel berjalan.
Tidak ada tabel/index/resource AWS baru atau perubahan IAM/Cognito/CORS/URL API.
STS_TABLE_NAME dan lambda_function.lambda_handler tetap. EC2 tetap stop.
Penggunaan API/Lambda/DynamoDB tetap mengikuti paket akun. Paralelisme memberi
beban bersamaan hingga tiga permintaan unduhan; bukan jaminan penghematan biaya.
Riwayat ringan/grafik tetap menggunakan jalur terpisah tanpa mengunduh landmark.
Retensi tetap 7 hari dan hanya pemilik sesi dapat membaca datanya.

## Validasi
35 tes backend dan 10 tes transport frontend lolos. TypeScript/Vite build lolos.
Uji lokal DynamoDB memakai ekspor sesi a24411c886b7d10e5d291093bfcbbcc5:
92 batch / 1.786 frame. Permintaan data mentah 31 → 10, dibagi menjadi 3 rentang
berisi masing-masing 3, 4, 3 request. Status awal tidak termasuk hitungan ini.
Seluruh batch, frame dan field persis sama dengan ekspor asli. Tes juga memeriksa
respons di luar urutan, progres naik, sesi kosong, kegagalan sebagian, retry,
penolakan celah/duplikat, retensi, privasi akun, dan batas ukuran respons.
Angka ini bukan hasil pengukuran waktu AWS. Kecepatan sebenarnya bergantung pada
jaringan, ukuran sesi dan respons AWS; tidak menjanjikan durasi tertentu.
Installer mencadangkan file yang ditimpa ke camera_cloud_backups.
