# Tiga hitungan latihan STS

Pembaruan tampilan untuk proyek kamera cloud yang sudah memakai ekspor v02 dan
Lambda v05. Tidak perlu mengganti kode Lambda atau konfigurasi AWS.

1. Ekstrak ZIP. Salin install_camera_cloud.py dan folder camera_cloud_payload ke
   folder proyek yang berisi api.py dan .venv-api. Gabungkan/timpa payload lama.
2. Di PowerShell folder proyek, jalankan:
   .\.venv-api\Scripts\python.exe install_camera_cloud.py
3. Buka http://localhost:8000/camera/?backend=cloud lalu Ctrl+F5.
   Backend lokal yang sudah berjalan boleh tetap berjalan.

Tiga kartu:
- Percobaan bangkit: jumlah percobaan yang sudah tercatat, ditambah satu ketika
  fase BANGKIT masih berlangsung. Termasuk bangkit yang belum lengkap. Gerakan
  condong/persiapan saja belum dihitung sebagai percobaan bangkit.
- Bangkit lengkap: jumlah yang memenuhi syarat berdiri dari acuan pribadi.
- Siklus selesai: bangkit lengkap kemudian kembali duduk.

Bangkit belum lengkap lalu duduk tetap dicatat sebagai percobaan, tetapi tidak
menambah bangkit lengkap atau siklus selesai. Kembali duduk bukan penghitung
terpisah. Postur MEMENUHI/BELUM MEMENUHI tetap ditampilkan pada hasil percobaan.

Pada JSON sesi a24411c886b7d10e5d291093bfcbbcc5, hasil akhir: 6 percobaan,
5 bangkit lengkap, 4 siklus selesai. Pembaruan ini tidak menghitung ulang data
atau mengubah aturan engine. Ketiga kartu juga tersedia di mode kamera lokal.
Pemantau MQTT lokal tetap menggunakan tampilan dan payload sebelumnya.

Ekspor bertahap dan tombol Unduh sesi cloud terakhir dari v02 tetap disertakan.
Installer mencadangkan file lama dalam camera_cloud_backups. Aset MediaPipe
yang sudah ada digunakan kembali. Build TypeScript/Vite sudah diperiksa.
