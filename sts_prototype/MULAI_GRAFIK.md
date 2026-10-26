# v0.8.0 — grafik sudut dan penanda fase

Versi ini melanjutkan kamera, API, MQTT dan pemantau HP v0.7.0. Grafik memakai pengukuran yang sudah dihitung oleh backend. Tidak ada perubahan aturan kalibrasi, penilaian, atau penghitungan STS.

## Memperbarui proyek

Hentikan backend dengan Ctrl+C. Ekstrak ZIP lalu salin ISI folder STS_TA_Camera_v08 ke D:\sts_prototype, setujui penggantian file kode. Simpan folder .venv-api, data dan results_api milikmu; ZIP tidak berisi ketiganya. Frontend sudah dibangun dan tidak memerlukan npm untuk dipakai.

Broker LAN v0.7.0 yang sudah berjalan boleh tetap dipakai. Jika perlu menjalankannya lagi, buka PowerShell pada D:\sts_prototype:

```powershell
& "C:\Program Files\mosquitto\mosquitto.exe" -c ".\mosquitto-lan.conf" -v
```

Di terminal backend pada folder yang sama:

```powershell
$env:STS_MQTT_ENABLED="1"
.\.venv-api\Scripts\python.exe -m uvicorn api:app --host 0.0.0.0 --port 8000
```

Jika kamu memilih folder baru tanpa venv, ikuti langkah instalasi MULAI_HP.md dahulu. Tidak ada dependency Python atau frontend baru untuk fitur grafik. Izin firewall dari v0.7.0 tidak perlu ditambahkan lagi.

## Tiga tempat grafik

### Kamera laptop

Buka http://127.0.0.1:8000/camera/ lalu refresh Ctrl+F5. Pastikan label v0.8.0. Jalankan kalibrasi dan latihan seperti sebelumnya. Gulir ke bagian **Grafik sudut sesi berjalan** di bawah panel kamera.

Grafik ini memakai hasil setiap frame HTTP yang diterima tab kamera. Tampilan menyimpan 120 detik terakhir, maksimal 2400 titik, sehingga tetap ringan. Saat memulai sesi baru, grafik langsung direset. Setelah sesi diakhiri, grafik tetap terlihat sampai kamu memulai sesi berikutnya/refresh.

### Pemantau MQTT di HP

Buka http://IP-LAPTOP:8000/camera/?view=monitor dan klik Hubungkan MQTT. Gunakan IP Wi-Fi laptop yang sekarang; contoh IP yang sebelumnya dipakai pengguna adalah 192.168.100.193, tetapi alamat dapat berubah. Refresh HP agar mendapatkan v0.8.0.

Bagian **Grafik sudut dari MQTT** mengikuti sesi yang dipilih pada pemantau. Buffer dipisahkan menurut session_id sehingga garis dua sesi tidak bercampur. Halaman menyimpan paling banyak 20 sesi, masing-masing 120 detik terakhir/maksimal 2400 titik. Grafik ini hanya berisi pesan yang benar-benar diterima tab, bukan seluruh frame sesi. Pesan normal sekitar setiap 0,5 detik dan ketika keadaan berubah. Karena itu grafik HP bisa lebih jarang daripada grafik kamera.

### Riwayat tersimpan

Klik **Buka riwayat latihan**, pilih satu sesi. Bagian **Grafik sudut sesi tersimpan** dibentuk dari seluruh frame di JSON yang tersimpan pada SQLite. Fitur ini juga tersedia di pemantau HP; pembacaan riwayat menggunakan API HTTP pada server yang sama, sedangkan grafik langsung tetap menggunakan MQTT.

Sesi versi lama yang sudah mempunyai timestamp dan measurement pada frames bisa digambarkan. Laporan penilaian sesi lama tidak dihitung ulang. Jika data tidak memiliki mode LATIHAN, centang Sertakan kalibrasi agar semua frame bertimestamp ditampilkan sebagai tahap tidak diketahui.

## Cara membaca

- Sumbu mendatar: detik sejak sesi dibuat. Awal LATIHAN bisa berada pada detik 30 atau lebih, bukan selalu detik nol.
- Sumbu tegak: sudut dalam derajat, 0–180°.
- Hijau: sudut lutut kiri; jingga: sudut badan–paha kiri; ungu: kemiringan badan terhadap vertikal.
- Pita bawah: duduk, persiapan, bangkit, berdiri. Abu-abu menunjukkan kalibrasi/kembali atau pengukuran tidak tersedia.
- Secara default hanya LATIHAN yang ditampilkan. Centang **Sertakan kalibrasi** untuk melihat sejak awal sesi.
- Centang/lepas nama sudut untuk menampilkan/menyembunyikan garisnya.
- Geser pengatur **Periksa waktu** atau arahkan penunjuk pada grafik untuk membaca sampel terdekat. Angka yang ditampilkan berasal dari sampel tersebut, bukan interpolasi nilai baru.
- Tombol **Ikuti data terbaru** mengembalikan penunjuk ke sampel terbaru pada grafik langsung.
- Di HP, geser grafik ke samping jika seluruh sumbu belum terlihat; pengatur waktu tetap berada di bawah grafik.

Garis terputus jika nilai pengukuran tidak tersedia atau jeda terlalu besar: lebih dari 0,3 detik untuk frame kamera/riwayat, lebih dari 1,5 detik untuk pesan MQTT yang lebih jarang. Pita fase berasal dari label yang dilaporkan sistem; pada MQTT, waktu perpindahan fase mengikuti pesan yang diterima. Titik satu-satunya pada suatu bagian ditampilkan sebagai titik kecil.

Untuk sesi panjang, titik gambar diringkas per bagian mendatar dengan mempertahankan nilai awal, akhir, minimum dan maksimum. Pembacaan penunjuk waktu tetap memakai titik sumber lengkap. JSON dan data SQLite tidak diperkecil.

Grafik menampilkan sudut geometri 2D yang telah dihaluskan. Grafik bukan prediksi LSTM atau pengukuran baru, dan tidak menambahkan keputusan klinis. Batas penilaian tetap asumsi pribadi seperti versi sebelumnya.

## Uji cepat

1. Uji langsung: hubungkan pemantau, lakukan satu siklus STS di kamera laptop. Periksa hitungan dan kurva di kedua perangkat.
2. Tanpa kamera: buka http://127.0.0.1:8000/simulation dan Jalankan simulasi 1 siklus. Grafik MQTT dan riwayat akan mencantumkan sesi Simulasi. Tab kamera tidak mengambil grafik simulasi karena memakai sesi kameranya sendiri.
3. Uji riwayat: setelah Akhiri & simpan, perbarui daftar riwayat dan pilih sesi. Grafik seharusnya tampil kembali, termasuk setelah backend direstart.
4. Uji data hilang: pada sesi kamera, saat tubuh tidak terbaca, garis harus terputus dan pembacaan menampilkan Tidak tersedia.

## Kode

- frontend/src/angle-data.ts: konversi frame/pesan menjadi titik, buffer langsung, pemisahan data hilang, peringkasan titik gambar.
- frontend/src/AngleChart.tsx: tiga kurva SVG, sumbu waktu, pita fase, pengatur waktu dan pemilihan garis.
- frontend/src/main.tsx: menambahkan hasil frame HTTP ke grafik kamera.
- frontend/src/MqttMonitor.tsx: buffer grafik per sesi dari pesan MQTT.
- frontend/src/History.tsx: membaca frame dari detail sesi tersimpan dan menampilkan grafik.

Untuk pengembang, tes logika grafik: dari frontend jalankan `node test-charts.mjs` setelah dependency npm tersedia. Tes backend seperti versi sebelumnya. Lihat HASIL_UJI_GRAFIK.md untuk hasil dan batas pengujian.
