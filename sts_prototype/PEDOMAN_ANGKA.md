# Catatan v0.4

Dokumen berikut adalah panduan versi lama. Untuk menjalankan web terbaru dan aturan pribadi, gunakan **MULAI_V04.md** dan **ATURAN_KALIBRASI.md**.

# Angka dan asal rancangan

PDF: Ringkasan_Pedoman_STS_dan_Toleransi.pdf, ringkasan diskusi 12 Oktober 2026. Tercantum di PDF tidak berarti terverifikasi dari artikel asli.

|Parameter|Nilai|Status|
|---|---|---|
|Kalibrasi duduk/berdiri|1 detik|Rancangan PDF|
|Condong minimum|25 derajat|Pilihan pengguna, interpretasi operasional referensi; bukan seluruh STS pasti benar|
|Kenaikan berdiri|90% perjalanan duduk-berdiri|Rancangan PDF; rumus diperjelas di diskusi|
|Tahan kondisi|0.3 detik|Rancangan PDF; juga dipakai untuk onset/rise/return sementara|
|Ambang mulai bangkit|baseline kecepatan + 3SD|Rancangan/analogi PDF dan diskusi; belum divalidasi|
|Toleransi duduk|10 derajat|Sementara; angka ini belum ditemukan dalam PDF|
|Toleransi lurus|15 derajat, sudut >=165|Sementara; PDF memakai X, belum ada X terukur|
|Kecepatan stabil|0.08 kenaikan/detik|Sementara; belum ditemukan dasar angka|
|Onset condong|baseline + max(3SD,3 derajat)|3SD ada dalam PDF; minimum 3 derajat sementara|
|Mulai naik|kenaikan >8%|Sementara|
|Kembali duduk|<=20%, hip <120|20% contoh rancangan PDF; 120 sementara|
|Tangan dekat paha|<12% torso|Sementara; peringatan saja|
|Kaki di bawah lutut|<=15% torso|Sementara|
|Visibility|>=0.65 tubuh|Sementara; kualitas pengamatan|
|Penghalusan|0.12 detik|Sementara|
|Selisih kalibrasi minimal|8% tinggi gambar|Pemeriksaan teknis sementara|
|Kembali duduk sebelum mulai|1 detik|Sementara|
|Batas galat evaluasi|5 derajat|Belum diterapkan sebagai aturan; analogi, bukan toleransi tubuh|
|Batas waktu percobaan|Belum ditetapkan|Tidak diterapkan|

Posisi kamera samping kiri dan landmark kiri tetap merupakan kondisi prototipe. Sudut proyeksi 2D, bukan sudut anatomis 3D. Noise alat tidak otomatis menentukan postur yang boleh diterima.

## Tambahan v0.4
- speed_window = 0.2 detik: jendela estimator kecepatan sementara (regresi linear kausal).
- sitting_window = 0.5 detik: jendela median duduk sementara; minimal 5 sampel dan rentang 80% jendela.
- Celah waktu >0.15 detik mengosongkan jendela kecepatan; nilai teknis sementara.
- Semua batas postur/deteksi utama sebelumnya tetap. Pengujian lama dipakai sebagai data pengembangan; perlu uji baru.

## Pengganti parameter pengolahan v0.5

Bagian ini menggantikan jumlah sampel dan batas celah di catatan v0.4:

|Parameter teknis|Nilai v0.5|Dasar|
|---|---|---|
|Jendela kecepatan|Nominal 0.2 detik; mempertahankan minimal 3 sampel, maksimal umur 0.6 detik pada konfigurasi default|Perbaikan dukungan pemrosesan lambat; belum tervalidasi|
|Celah pengamatan maksimum|0.3 detik; lebih besar mereset sampel/timer|Rancangan teknis sementara, bukan nilai dari PDF|
|Median duduk|0.5 detik, rentang ≥0.4 detik, minimal 3 sampel|Mendukung sampel jarang; belum tervalidasi|
|Perekaman kalibrasi|Minimal 1 detik dan 9 sampel diterima berturut-turut|Menjamin cukup keluaran estimator; belum menjamin postur benar/noise stabil|

Tidak ada perubahan batas postur, condong, tinggi berdiri, atau kecepatan stabil. Jendela lebih panjang bisa mengubah respons waktu: kalibrasi ulang dan uji pada rekaman baru. Pemilihan Full/Heavy tidak mengubah aturan penilaian.

## Tambahan v0.5.1

- Bukti asal untuk hitungan: progress ≤20% dan hip <120° selama 0.3 detik. Tidak mewajibkan postur duduk ideal.
- Usia bukti asal dan snapshot duduk maksimum 2 detik saat onset (seated_evidence_max_age). Parameter rekayasa baru, bukan angka dari PDF/jurnal; belum tervalidasi.
- Titik hilang membatalkan snapshot asesmen aktif dan timer tahan, tetapi asal duduk yang masih relevan dapat dipakai untuk melacak hitungan. Snapshot historis tidak digunakan menilai kualitas setelah gangguan.
- Kondisi akhir berdiri dan seluruh batas postur sebelumnya tetap. Memisahkan hitungan dari kualitas tidak menjadikan semua repetisi otomatis memenuhi aturan.

## Perubahan alur v0.5.2

PERSIAPAN menggantikan CONDONG. Persiapan tanpa kenaikan yang terkonfirmasi tidak menjadi hasil percobaan STS. Percobaan terkonfirmasi pada kecepatan >ambang kalibrasi dan progress >8% selama 0.3 detik, memakai aturan naik yang sudah ada. Penghitungan bangkit teramati dipisahkan dari konfirmasi berdiri lengkap dan konfirmasi siklus. Tidak ada perubahan batas sudut atau visibility.

Berdiri yang kehilangan data diberi status BELUM DAPAT DIKONFIRMASI, bukan kegagalan yang sudah terbukti. Tidak menambah hitungan berdiri lengkap/siklus terkonfirmasi, tetapi kenaikan dan kembali duduk yang teramati tetap dilaporkan. Tidak mengisi landmark hilang atau menganggap gerakan pasti benar. Lihat README untuk definisi kolom null dan hitungan baru.

## Tambahan v0.5.4

Standing_window = 0.5 detik adalah jendela teknis sementara, dipilih dalam pengembangan kasus berdiri yang tertahan jitter kecepatan. Syarat jalur plateau: >=3 sampel, cakupan >=0.4 detik, kemiringan regresi absolut <=0.08 perjalanan/detik, rentang progress <=0.04 (=0.08 x 0.5). Jalur cepat jendela pendek tetap tersedia; salah satu jalur boleh memenuhi kestabilan. Tinggi/sudut dan hold 0.3 detik tetap wajib. Ini mengubah algoritma konfirmasi, walaupun nilai ambang sudut dan kecepatan tidak berubah. Belum ada validasi independen atau dasar klinis untuk parameter plateau ini.

Tangan: konteks dibatasi pada persiapan/bangkit sebelum plateau tegak. Jarak <0.12 torso, visibility >=0.65, timer on/off 0.15/0.20 detik dari v0.5.3 tetap. Seluruhnya parameter prototipe; tidak mengukur gaya tumpuan.

## Keputusan v0.5.5

PDF dipakai sebagai acuan operasional sesuai keputusan pengguna, termasuk interpretasi condong minimum >=25°. Tidak menghapus keputusan keseluruhan. Toleransi duduk 10° dan lurus 15° tetap sementara karena PDF menyebut X, belum diukur independen. Anotasi manual 12 frame hanya pemeriksaan awal kesesuaian sudut proyeksi 2D; tidak menentukan X atau akurasi keputusan keseluruhan. Tidak menggunakan Zhao 2017. Acuan jurnal utama adalah Kerr, Clark, Pomeroy 2019 (DOI 10.1177/1545968319846119), pasien pasca stroke, terpisah dari Kerr 1997.

Bantuan tangan ditunda dan tidak diproses oleh app.py. Rekaman input tanpa overlay menggunakan MJPG AVI; FPS putar tetap, penanda waktu asli di frames CSV. Data mentah belum EMA disimpan per frame. Tidak ada pelonggaran ambang atau perubahan algoritma hitungan/berdiri dari v054.

## Perubahan v0.5.6

Konfirmasi bangkit menambahkan syarat keluar dari rentang duduk: progress > seated_progress (default 0.2), sesudah kandidat kecepatan/progress >0.08 selama 0.3 detik. Bukan ambang baru dari Kerr/PDF untuk seat-off; parameter deteksi teknis untuk menghindari salah hitung pergeseran kecil. Upaya sangat kecil yang tetap di rentang duduk tidak dikonfirmasi sebagai bangkit.

Jalur tambahan bukti duduk memakai sitting_window=0.5 detik, cakupan >=0.4 detik/3 sampel, slope absolut <=stable_speed=0.08 dan excursion <=stable_speed*sitting_window=0.04. Hanya posisi duduk dekat baseline yang masuk jendela. Ambang duduk 90 +/-10, lean/thigh <=10 dan kaki <=0.15 tetap. Snapshot terbaru yang valid dapat berbeda waktunya dari versi lama, sehingga median/label komponen bisa berubah. Tidak mempertahankan jendela melintasi data hilang. Semua ini rancangan teknis, bukan estimasi galat alat atau batas klinis yang baru.
