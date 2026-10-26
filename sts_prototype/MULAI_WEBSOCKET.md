# v0.6.0 — pemantau hasil STS melalui MQTT lewat WebSocket

Melanjutkan v0.5.0: hasil yang diterima subscriber Python kini dapat ditampilkan di tab browser kedua. Kamera/MediaPipe tetap bekerja di tab latihan; landmark tetap dikirim ke FastAPI melalui HTTP. Backend mengirim hasil ke broker melalui MQTT TCP 1883. Broker yang sama meneruskan pesan ke tab pemantau melalui MQTT lewat WebSocket 9001. Semuanya masih di satu laptop.

## Persiapan

Hentikan backend lama dan broker lama dengan Ctrl+C di masing-masing terminal. Ekstrak ZIP, buka PowerShell di folder STS_TA_Camera_v06 yang berisi api.py dan mosquitto-local.conf. Untuk membawa riwayat, salin folder data dan results_api dari proyek lama saat backend sudah berhenti.

Jika .venv-api belum ada dalam folder baru:

```powershell
py -3.11 -m venv .venv-api
```

Lalu instal:

```powershell
.\.venv-api\Scripts\python.exe -m pip install -r requirements-api.txt
```

Python 3.12 juga dapat digunakan dengan mengganti -3.11 menjadi -3.12. Frontend sudah dibangun di ZIP; tidak perlu menginstal Node/npm untuk menjalankannya.

## Terminal 1: broker dengan dua koneksi

Jalankan dari folder proyek baru supaya file konfigurasi ditemukan:

```powershell
& "C:\Program Files\mosquitto\mosquitto.exe" -c ".\mosquitto-local.conf" -v
```

Biarkan terbuka. Konfigurasi ini menjalankan SATU broker dengan listener TCP 1883 dan WebSocket 9001. Keduanya hanya untuk koneksi dari laptop yang sama. Jangan menjalankan dua broker terpisah untuk kedua port itu, karena pesan tidak otomatis dibagikan antarbroker.

Jika port 1883 sedang dipakai, pastikan broker terminal lama sudah dihentikan. Jika Mosquitto berjalan sebagai Windows service, hentikan service Mosquitto melalui aplikasi Services Windows dahulu (mungkin memerlukan administrator), kemudian jalankan perintah di atas. Jangan menghentikan proses lain yang tidak dikenal. Jika muncul error dukungan WebSocket, gunakan installer Windows dari https://mosquitto.org/download/ yang mendukung listener websockets.

## Terminal 2: backend

Di PowerShell kedua, tetap di folder proyek baru:

```powershell
$env:STS_MQTT_ENABLED="1"
.\.venv-api\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000
```

## Dua tab browser

1. Buka http://127.0.0.1:8000/camera/?view=monitor dan klik **Hubungkan MQTT**. Tunggu status TERHUBUNG.
2. Buka http://127.0.0.1:8000/camera/ di tab kedua, aktifkan kamera.
3. Lakukan kalibrasi duduk, kalibrasi berdiri, lalu kembali duduk sampai LATIHAN.
4. Lakukan satu kali duduk → berdiri → duduk. Amati hitungan pemantau menjadi 1 bangkit dan 1 siklus.
5. Akhiri & simpan di tab kamera. Pemantau menampilkan Sesi selesai bila pesan penutupan diterima.

Untuk uji saluran tanpa kamera, gunakan http://127.0.0.1:8000/simulation di tab kedua dan klik Jalankan simulasi 1 siklus. Pemantau akan menandai sumber sebagai Simulasi. Ini pengujian koneksi, bukan akurasi pengenalan gerakan.

Subscriber Python tetap opsional dan dapat dijalankan di terminal ketiga dengan perintah dari v0.5.0; ia akan menerima pesan broker yang sama. Jangan jalankan mqtt_publisher.py contoh selama mengamati sesi kamera.

## Cara membaca pemantau

- Nama sesi membedakan sesi lama dan sesi baru. Pilih sesi tertentu jika tidak ingin mengikuti pesan sesi terbaru.
- Angka sudut dan hitungan berasal dari pesan MQTT, tanpa mengambil hasil dari API.
- Data terakhir tetap terlihat jika koneksi terputus; keterangannya menyebut koneksi terputus/umur pesan. Setelah lebih dari 3 detik tanpa pesan baru, pemantau memberi keterangan.
- Jika sesi selesai, labelnya Sesi selesai. Angka yang tampil adalah hasil terakhir diterima, bukan pengukuran baru.
- Format pesan latihan manual yang berbeda akan diabaikan. Payload STS harus memakai schema_version=1 dan session_id yang dibuat backend.
- Pemantau menyimpan paling banyak 20 sesi dan 30 pesan terbaru dalam memori tab. Tidak menambah tabel SQLite. Refresh menghapus tampilan sementara; tunggu pesan berikutnya atau mulai sesi baru.
- QoS 0 dan retain=false sama seperti v0.5.0: tidak menjamin setiap pesan diterima. Buka pemantau sebelum memulai sesi. Hasil tersimpan tetap tersedia di riwayat halaman kamera.
- Jika MQTT terputus, kamera dan API tetap bekerja. Pemantau mencoba menyambung kembali otomatis setiap 2 detik. Tombol Putuskan menghentikan percobaan sambungan.

## Apa yang dipelajari

MQTT mengatur pesan melalui topic dan broker. WebSocket membawa pesan MQTT antara browser dan broker. Backend Python menggunakan koneksi MQTT TCP biasa; keduanya bertemu di broker yang sama. Halaman pemantau tidak memakai WebSocket langsung ke FastAPI.

Kode yang berperan: mosquitto-local.conf mengaktifkan dua listener; mqtt_bridge.py mengirim hasil dari Python; frontend/src/MqttMonitor.tsx memakai MQTT.js untuk menerima pesan; telemetry.ts memvalidasi format; main.tsx memilih halaman kamera atau pemantau. Aturan STS personal tetap seperti v0.4.2.

Referensi: https://github.com/mqttjs/MQTT.js dan https://mosquitto.org/man/mosquitto-conf-5.html
