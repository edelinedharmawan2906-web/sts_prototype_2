# STS Kamera v0.5.0 — MQTT hasil analisis

Versi ini melanjutkan v0.4.2. Aturan kalibrasi, penilaian, JSON dan SQLite tetap memakai implementasi v0.4.2. Pengiriman landmark dari web ke FastAPI tetap melalui HTTP. MQTT menambahkan saluran hasil analisis: backend Python → Mosquitto → subscriber Python.

## Persiapan Windows

Hentikan backend lama dengan Ctrl+C. Ekstrak ZIP lalu buka PowerShell di folder yang berisi api.py. Jika ingin membawa riwayat, salin folder data dan results_api dari proyek lama saat backend sudah berhenti.

Jika .venv-api belum ada di folder ini:

```powershell
py -3.11 -m venv .venv-api
```

Instal dependensi menggunakan Python dari venv tersebut:

```powershell
.\.venv-api\Scripts\python.exe -m pip install -r requirements-api.txt
```

Python 3.12 juga bisa digunakan dengan mengganti -3.11 menjadi -3.12. Tidak perlu mengaktifkan venv karena perintah memanggil Python di dalamnya secara langsung.

## Tiga terminal

Terminal 1, broker (jika sudah berjalan, gunakan yang ada):

```powershell
& "C:\Program Files\mosquitto\mosquitto.exe" -v
```

Terminal 2, penerima (jalankan dari folder proyek baru):

```powershell
.\.venv-api\Scripts\python.exe mqtt_subscriber.py
```

Tunggu tulisan `Siap menerima hasil STS pada sts/latihan`.

Terminal 3, backend (dari folder proyek baru):

```powershell
$env:STS_MQTT_ENABLED="1"
.\.venv-api\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Buka http://127.0.0.1:8000/camera/ lalu jalankan kamera, kalibrasi duduk dan berdiri, kembali duduk, dan lakukan STS. Amati data di terminal 2. Jika hanya menguji koneksi tanpa kamera, buka http://127.0.0.1:8000/simulation dan jalankan simulasi satu siklus. Pesan simulasi diberi input_source=simulation.

Tidak perlu menjalankan mqtt_publisher.py contoh: api.py sekarang yang mengirim hasil otomatis.

## Memahami data

Topic: `sts/latihan`. Setiap pesan mencantumkan session_id dan input_source. t adalah detik sejak awal sesi. mode adalah tahap kalibrasi/latihan, phase adalah fase mesin gerakan; selama kalibrasi perhatikan mode. knee_angle, hip_angle, trunk_lean berasal dari pengukuran geometri 2D yang telah dihaluskan, satuannya derajat. complete menghitung bangkit mencapai acuan berdiri pribadi, cycles menghitung siklus kembali duduk. Kedua hitungan ini bukan jumlah gerakan yang lolos seluruh aturan postur. pose_valid=false berarti pengukuran tidak tersedia; sudut saat itu null. closed=true berarti sesi telah diakhiri.

Pesan dikirim sekitar setiap 0,5 detik selama frame masuk, serta ketika mode, fase, hitungan, validitas pose, atau status selesai berubah. Ini bukan rekaman seluruh frame. MQTT menggunakan QoS 0, retain=false untuk latihan data langsung; penerima yang terlambat tidak memperoleh seluruh pesan sebelumnya. Riwayat lengkap tetap disimpan di JSON/SQLite setelah tombol Akhiri.

Periksa http://127.0.0.1:8000/health: mqtt.enabled dan mqtt.connected harus true. queued_messages menghitung pesan yang diterima antrean kirim Paho selama backend berjalan; bukan bukti bahwa subscriber sudah menerima pesan.

Jika broker mati, kamera/API tetap bekerja dan koneksi MQTT dicoba lagi otomatis. Pesan saat terputus dilewati. Setelah tersambung, frame berikutnya mengirim keadaan terbaru. Jangan gunakan MQTT latihan ini untuk menjamin pengiriman laporan akhir. Jika halaman kamera belum berganti ke v0.5.0, refresh dengan Ctrl+F5 dan periksa folder terminal backend.

Untuk menjalankan tanpa MQTT, di terminal backend gunakan `$env:STS_MQTT_ENABLED="0"` sebelum menjalankan Uvicorn. Variabel lingkungan berlaku untuk terminal itu dan proses turunannya.

## Kode yang berperan

- api.py: menerima landmark HTTP, menjalankan analisis, meneruskan hasil ke bridge.
- mqtt_bridge.py: koneksi Paho di thread latar, pembatasan frekuensi, format JSON, publikasi.
- mqtt_subscriber.py: koneksi penerima dan pencetakan pesan.
- personal_engine.py: penghasil fase dan hitungan; aturan tetap seperti v0.4.2.

Referensi API Paho: https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html
