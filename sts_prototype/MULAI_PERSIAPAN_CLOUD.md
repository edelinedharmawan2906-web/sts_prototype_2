# v0.8.1 — Pengaturan untuk persiapan cloud

Ini tahap persiapan kode. Belum ada server cloud yang dipasang.
Paket ini belum untuk dipublikasikan: autentikasi API/riwayat dan broker,
HTTPS/WSS, serta penyimpanan server masih harus disiapkan terlebih dahulu.

## 1. Perbarui proyek lokal

Hentikan backend dengan Ctrl+C. Salin isi folder paket ke D:\sts_prototype,
timpa kode lama. Pertahankan .venv-api, data, dan results_api milikmu.
Frontend sudah dibuild; tidak perlu memasang Node untuk menjalankannya.

## 2. Jalankan secara lokal seperti sebelumnya

Mosquitto di terminal pertama:

```powershell
cd D:\sts_prototype
& "C:\Program Files\mosquitto\mosquitto.exe" -c ".\mosquitto-lan.conf" -v
```

Backend di terminal kedua:

```powershell
cd D:\sts_prototype
$env:STS_MQTT_ENABLED="1"
$env:STS_MQTT_HOST="127.0.0.1"
$env:STS_MQTT_PORT="1883"
Remove-Item Env:STS_MQTT_WS_URL -ErrorAction SilentlyContinue
.\.venv-api\Scripts\python.exe -m uvicorn api:app --host 0.0.0.0 --port 8000
```

Kalau dependency lama belum lengkap:

```powershell
.\.venv-api\Scripts\python.exe -m pip install -r requirements-api.txt
```

## 3. Periksa konfigurasi

Buka http://127.0.0.1:8000/runtime-config
Hasil normal lokal: {"mqtt_ws_url":null}.
Artinya alamat broker otomatis mengikuti nama host halaman web, port 9001.
Di laptop buka kamera melalui http://127.0.0.1:8000/camera/.
Di HP buka http://IP-LAPTOP:8000/camera/?view=monitor, lalu Hubungkan MQTT.
Refresh dengan Ctrl+F5 di laptop agar JavaScript baru dimuat.

Untuk menguji konfigurasi khusus secara lokal, hentikan backend, lalu jalankan
blok perintah backend tadi setelah menambahkan:

```powershell
$env:STS_MQTT_WS_URL="ws://192.168.100.193:9001"
```

Gunakan IPv4 laptop yang sebenarnya. /runtime-config sekarang menampilkan URL
tersebut; detail koneksi monitor harus menampilkan URL yang sama.
Nilai environment dibaca oleh proses backend. Perubahan PowerShell memerlukan
restart backend dan refresh halaman monitor. Setelah uji, hapus variabel untuk
kembali ke pemilihan alamat otomatis.

## Apa yang berubah dan mengapa?

- api.py menyediakan GET /runtime-config, hanya berisi alamat publik MQTT.
- frontend/src/runtime-config.ts mengambil alamat broker dari API.
- MqttMonitor.tsx memakai pengaturan tersebut saat tombol Hubungkan ditekan.
- STS_MQTT_HOST dan STS_MQTT_PORT tetap alamat TCP dari Python menuju broker.
- STS_MQTT_WS_URL adalah alamat WebSocket yang dapat dijangkau browser.
- API sesi dan riwayat tetap memakai domain yang sama dengan halaman web,
  sehingga tidak memerlukan konfigurasi domain API terpisah atau CORS baru.
- Saat halaman HTTPS digunakan, broker harus WSS. Default HTTPS adalah
  wss://DOMAIN-HALAMAN/mqtt. Jalur /mqtt harus diarahkan ke broker oleh reverse
  proxy saat deployment; kode ini belum menyiapkan reverse proxy itu.
- Jangan masukkan username/password ke STS_MQTT_WS_URL. Endpoint ini publik.
  Dukungan login broker/browser belum ditambahkan pada tahap ini.
- Kalibrasi, penilaian STS, format pesan, dan grafik tetap menggunakan logika v08.

## Tahap berikutnya setelah tes lokal

Tentukan server dan domain yang akan digunakan. Kemudian siapkan autentikasi,
reverse proxy HTTPS/WSS, broker dengan izin akses per pengguna, dan storage
persisten untuk data serta results_api. Jalankan backend satu worker karena sesi
aktif masih berada dalam RAM. Restart backend akan menghilangkan sesi aktif;
riwayat yang sudah disimpan tetap ada jika storage dipertahankan.

Jangan membuka port router atau menerbitkan prototype tanpa autentikasi.
Server dapat menyajikan frontend dan API pada domain yang sama. Browser tetap
menjalankan kamera/MediaPipe, lalu mengirim landmark melalui HTTPS; Python
melakukan analisis dan mengirim hasil melalui broker menuju monitor.
