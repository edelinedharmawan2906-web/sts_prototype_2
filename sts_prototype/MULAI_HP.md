# v0.7.0 — kamera laptop, pemantau di HP

Target: kamera laptop → FastAPI laptop → Mosquitto laptop → pemantau browser HP. Laptop dan HP memakai Wi-Fi yang sama. Ini latihan jaringan lokal; mode ini belum memakai login. Gunakan Wi-Fi pribadi yang kamu percayai.

## 1. Perbarui folder kerja

Hentikan backend dan broker lama dengan Ctrl+C. Ekstrak ZIP. Jika folder kerjamu D:\sts_prototype, salin ISI folder STS_TA_Camera_v07 ke D:\sts_prototype dan setujui penggantian file kode. Folder .venv-api, data, results_api milikmu tetap dipakai; ZIP tidak berisi ketiganya. Buka PowerShell di D:\sts_prototype.

Jika memakai folder baru yang belum memiliki venv, buat dulu:

```powershell
py -3.11 -m venv .venv-api
```

Instal/perbarui dependensi:

```powershell
.\.venv-api\Scripts\python.exe -m pip install -r requirements-api.txt
```

Frontend sudah dibangun. Tidak perlu Node/npm untuk menjalankan aplikasi.

## 2. Terminal 1: broker LAN

```powershell
& "C:\Program Files\mosquitto\mosquitto.exe" -c ".\mosquitto-lan.conf" -v
```

Biarkan terbuka. Harus berhasil membuka 1883 dan 9001 tanpa terminating. Jangan gunakan mosquitto-local.conf untuk HP karena listener WebSocket pada konfigurasi itu hanya menerima koneksi dari laptop sendiri. TCP 1883 tetap hanya untuk Python laptop; yang diakses HP adalah WebSocket 9001.

Jika port 1883 masih dipakai, hentikan broker terminal sebelumnya atau service Mosquitto Broker melalui Services Windows, lalu jalankan ulang. Tidak perlu membuka port 1883 di firewall untuk HP.

## 3. Terminal 2: backend menerima jaringan lokal

```powershell
$env:STS_MQTT_ENABLED="1"
.\.venv-api\Scripts\python.exe -m uvicorn api:app --host 0.0.0.0 --port 8000
```

0.0.0.0 adalah alamat untuk server mendengarkan koneksi, bukan alamat yang diketik di browser. Laptop tetap membuka kamera dari http://127.0.0.1:8000/camera/ agar akses kamera browser tersedia. Jangan menjalankan kamera melalui alamat HTTP IP jaringan di HP; pada tahap ini HP hanya pemantau.

## 4. Izin firewall, sekali saja

Pada Wi-Fi rumah/pribadi yang kamu percayai, pastikan Windows Settings → Network & internet → Wi-Fi → jaringan aktif → Network profile type adalah Private. Jangan mengubah jaringan umum menjadi Private hanya untuk latihan ini.

Buka PowerShell dengan Run as administrator. Tambahkan aturan khusus port 8000 dan 9001 untuk profil Private dan sumber LocalSubnet:

```powershell
New-NetFirewallRule -DisplayName "STS latihan LAN" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000,9001 -Profile Private -RemoteAddress LocalSubnet
```

Cukup jalankan sekali. Tidak perlu mematikan Windows Firewall. 

Untuk menghapus aturan yang dibuat oleh perintah ini saat tidak diperlukan, gunakan PowerShell administrator:

```powershell
Get-NetFirewallRule -DisplayName "STS latihan LAN" | Remove-NetFirewallRule
```

## 5. Cari alamat laptop

Di PowerShell biasa:

```powershell
ipconfig
```

Cari IPv4 Address pada adapter Wi-Fi aktif (yang mempunyai Default Gateway), bukan adapter VPN/virtual. Misalnya 192.168.1.10. Gunakan alamat laptopmu yang sebenarnya; contoh ini bukan nilai wajib.

## 6. Buka dari HP

Hubungkan HP ke Wi-Fi yang sama. Di browser HP ketik, dengan IP laptop yang ditemukan:

```text
http://192.168.1.10:8000/camera/?view=monitor
```

Klik Hubungkan MQTT dan tunggu TERHUBUNG. Pemantau otomatis memakai ws://192.168.1.10:9001, bukan 127.0.0.1 milik HP. Buka pemantau sebelum memulai sesi agar pesan langsung ikut diterima.

Di laptop buka http://127.0.0.1:8000/camera/ dan pastikan label v0.7.0. Lakukan kalibrasi lalu latihan seperti sebelumnya. Kamera hanya aktif di laptop. Target hasil: 1 bangkit dan 1 siklus di laptop, serta 1/1 di pemantau HP.

Untuk mengecek koneksi tanpa gerakan, dari laptop buka http://127.0.0.1:8000/simulation dan klik Jalankan simulasi 1 siklus. HP akan menampilkan sumber Simulasi dan hasil 1/1. Ini uji koneksi, bukan uji akurasi gerakan.

## Jika belum terhubung

- Halaman HP sama sekali tidak terbuka: pastikan IP benar, Uvicorn memakai --host 0.0.0.0, Wi-Fi sama, dan firewall mengizinkan 8000. Coba buka http://IP-LAPTOP:8000/health dari HP.
- Halaman terbuka tetapi MQTT gagal: pastikan mosquitto-lan.conf dipakai dan port 9001 diizinkan. Dari laptop, Test-NetConnection IP-LAPTOP -Port 9001 seharusnya True. Tes dari laptop hanya membuktikan listener lokal dapat dihubungi, belum membuktikan jalur HP bebas hambatan.
- Terhubung tetapi belum ada pesan: cek http://127.0.0.1:8000/health pada laptop. mqtt.enabled dan mqtt.connected harus true. Jalankan sesi baru atau simulasi. Pesan sesi lama tidak dikirim ulang.
- Jaringan kampus/tamu bisa membatasi komunikasi antarperangkat meskipun nama Wi-Fi sama. Gunakan jaringan pribadi yang mengizinkan perangkat saling berkomunikasi. Hindari VPN yang mengubah rute selama tes.
- Jika IP laptop berubah setelah pindah Wi-Fi, cari ulang dengan ipconfig dan ubah URL di HP.
- Jika tampilan lama muncul, refresh. Pastikan frontend/dist dan api.py berasal dari v0.7.0.

Riwayat lengkap tetap disimpan oleh backend setelah Akhiri & simpan. Pemantau HP hanya menerima pesan langsung, QoS 0 tanpa retain seperti v0.6.0. Setelah tab ditutup/refresh, tunggu pesan baru.

## Kode yang berubah

- frontend/src/MqttMonitor.tsx: hostname broker mengikuti location.hostname pada URL yang dibuka. Browser laptop mengarah ke laptop sendiri; browser HP mengarah ke IP laptop.
- mosquitto-lan.conf: listener WebSocket dapat menerima koneksi jaringan.
- Backend menggunakan perintah --host 0.0.0.0; aturan dan perhitungan STS tidak diubah.

Referensi: https://learn.microsoft.com/en-us/powershell/module/netsecurity/new-netfirewallrule dan https://mosquitto.org/man/mosquitto-conf-5.html
