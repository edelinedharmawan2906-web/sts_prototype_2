# Pembaruan pengambilan duduk v0.4.2

Pengambilan cuplikan tidak lagi dibatasi kemiringan acuan+5°. Ambang +5° tetap hanya untuk mengenali fase persiapan, bukan untuk mengizinkan pengumpulan data.

- Gunakan data valid ketika pinggul berada dalam pita duduk (progress ≤0,20), pada fase DUDUK/PERSIAPAN.
- Jendela kestabilan sekitar 0,5 detik (minimal cakupan 80% dan 3 sampel), dengan besar laju perubahan progress ≤0,08 rentang/detik serta rentang progress ≤0,04 pada jendela default.
- Rentang perubahan hip/lean/thigh dalam jendela maksimal 10°; rasio kaki maksimal 0,10. Ini memeriksa perubahan, bukan membatasi besar sudut terhadap kalibrasi.
- Parameter kestabilan ini terpisah dari toleransi penilaian: sitting_capture_angle_range dan sitting_capture_ankle_range pada personal_rules.json.
- Simpan cuplikan teramati sebelum awal gerakan; usia bukti maksimal 2 detik saat dipilih. Jika awal persiapan belum mempunyai cuplikan, izinkan mengumpulkan cuplikan stabil ketika masih di posisi rendah, lalu pilih sebelum awal kenaikan pinggul.
- Setelah cuplikan awal tersedia, bekukan selama persiapan agar posisi sengaja condong sesudahnya tidak menggantikan posisi awal. Bukti yang dibekukan boleh lebih tua saat gerakan selesai; gap pengamatan tetap membuat penilaian keseluruhan tidak pasti.
- Jangan mengambil cuplikan yang waktunya sesudah awal kenaikan pinggul. rise_start_time dan sitting_capture_version ikut disimpan untuk penelusuran.
- Data yang tidak memenuhi toleransi tetap disimpan dan diberi hasil belum memenuhi. Data yang benar-benar tidak cukup tetap belum dapat dinilai.

Toleransi penilaian duduk, target tambahan kemiringan, syarat berdiri dan hitungan tetap seperti v0.4. Catatan historis di bawah memuat rincian lainnya; pembaruan pengambilan cuplikan di atas menggantikan bagian pemilihan cuplikan versi lama.

---

# Aturan pribadi v0.4 — asumsi teknis IIPP

Semua angka pada mode personal_dummy_v1 adalah pilihan pengembangan untuk latihan teknis, bukan batas klinis atau klaim dari jurnal. Acuan adalah postur yang direkam, bukan bukti kemampuan maksimum atau postur ideal.

## 1. Pengambilan acuan

Tekan Rekam duduk atau Rekam berdiri. Hitung mundur default 10 detik (pilihan 5/10/15/20). Tubuh belum harus terdeteksi ketika tombol ditekan. Setelah hitung mundur:

- Kumpulkan minimal 2 detik data kontinu dengan minimal 20 sampel valid. Jendela dibatasi sekitar 2–2,3 detik agar pengumpulan tidak terus bertambah.
- Visibility bahu, pinggul, lutut, dan pergelangan kaki kiri masing-masing minimal 0,65 (pemeriksaan lama).
- Jeda lebih dari 0,3 detik atau pose hilang mengulang pengumpulan sampel.
- Rentang posisi vertikal pinggul dalam jendela maksimal 3% tinggi gambar.
- Rentang setiap sudut hip/knee/lean/thigh maksimal 10°; rentang rasio kaki maksimal 0,10 panjang torso.
- Bila belum stabil, jendela bergeser dan menunggu posisi diam.
- Simpan median, simpangan baku, jumlah sampel, dan durasi jendela. Menggunakan pengukuran mentah yang valid, sebelum smoothing tampilan.

Kalibrasi duduk menyimpan tinggi pinggul, sudut lutut, badan–paha, kemiringan badan/paha dan rasio kaki. Kalibrasi berdiri menyimpan pengukuran yang sama. Suatu pengukuran disimpan tidak berarti semuanya digunakan untuk lulus/gagal.

Untuk menerima acuan berdiri, pinggul harus lebih tinggi minimal 8% tinggi gambar dibanding acuan duduk. Sudut lutut DAN badan–paha masing-masing perlu bertambah minimal 10° dibanding acuan duduk. Tidak ada syarat harus mencapai 165°. Jika gagal, pengambilan berdiri tetap aktif untuk diulang.

## 2. Pemeriksaan posisi duduk sebelum bangkit

| Pengukuran | Aturan |
| --- | --- |
| Badan–paha | Selisih terhadap median kalibrasi duduk maksimal ±10° |
| Kemiringan badan | Selisih terhadap median kalibrasi duduk maksimal ±10° |
| Kemiringan paha | Selisih terhadap median kalibrasi duduk maksimal ±10° |
| Posisi kaki | Selisih rasio terhadap median kalibrasi duduk maksimal ±0,10 panjang torso |

Contoh rasio kaki saat kalibrasi 0,25: nilai latihan 0,15–0,35 memenuhi aturan ini. Nilai 0,10 adalah toleransi terhadap panjang torso, bukan 10% dari rasio acuan 0,25.

Rasio kaki tetap |x_ankle−x_knee|/panjang_torso. Karena nilainya absolut, perubahan arah dari depan ke belakang tidak dibedakan oleh metrik ini.

Sampel awal diambil dari jendela duduk stabil sekitar 0,5 detik, dengan bukti terakhir maksimal 2 detik sebelum bangkit. Jika tidak tersedia, hasil postur awal belum dapat dinilai.

## 3. Persiapan dan deteksi bangkit

- Persiapan dikenali saat kemiringan melebihi acuan duduk +5°, dengan asal duduk yang baru diamati.
- Target kemiringan: puncak selama persiapan DAN bangkit minimal acuan duduk +10°. Contoh acuan 15° → puncak minimal 25°. Acuan 0° → minimal 10°.
- Ini pertambahan besar kemiringan pada gambar 2D, bukan pengukuran kelengkungan tulang belakang atau bukti arah condong anatomis.
- Kecepatan awal bangkit: maksimum antara 0,01 rentang kalibrasi/detik dan rerata kecepatan saat kalibrasi duduk +3×SD. Jendela estimasi kecepatan 0,2 detik.
- Kenaikan perlu keluar dari pita duduk (progress >0,20), disertai bukti kenaikan yang bertahan 0,3 detik. Bergoyang atau hanya condong tidak langsung menjadi bangkit.
- Asal duduk untuk hitungan membutuhkan progress ≤0,20 dan sudut badan–paha dalam ±20° dari kalibrasi duduk. Gate ±20° ini untuk mengenali asal gerakan; penilaian postur tetap ±10°.

## 4. Konfirmasi acuan berdiri pribadi

Semua syarat berikut harus terpenuhi:

1. Progress kenaikan pinggul ≥0,90. Rumus progress=(y_duduk−y_sekarang)/(y_duduk−y_berdiri).
2. Sudut lutut ≥ acuan lutut berdiri −10°.
3. Sudut badan–paha ≥ acuan badan–paha berdiri −10°.
4. Kecepatan perubahan progress ≤0,08 rentang kalibrasi/detik, atau lulus pemeriksaan plateau stabil yang sama batasnya.
5. Syarat-syarat bertahan selama 0,3 detik tanpa data terputus.

Contoh acuan lutut 155° → syarat sudut lutut minimal 145°. Sudut lebih besar daripada acuan boleh. Toleransi berdiri adalah batas bawah, bukan interval ±10°.

Satu konfirmasi menambah bangkit lengkap satu kali. Belum bisa menambah lagi sampai kembali duduk. Kembali duduk dikenali ketika progress ≤0,20 dan badan–paha dekat acuan duduk (±20°), bertahan 0,3 detik; saat itu siklus bertambah. Setelah kalibrasi, kesiapan awal kembali duduk membutuhkan 1 detik.

Kegagalan postur duduk atau target kemiringan tidak menghalangi hitungan bangkit bila acuan berdiri terkonfirmasi. Keduanya dilaporkan terpisah. Pengamatan terputus dapat membuat hasil belum dapat dinilai, bukan otomatis gagal. Bantuan tangan belum dinilai.

## 5. Konfigurasi, data, dan batas penggunaan

- Edit personal_rules.json untuk angka aturan pribadi. File dibaca saat sesi baru dibuat. Restart backend dan mulai sesi baru setelah perubahan.
- config.json tetap berisi pengaturan mesin dasar/kompatibilitas aplikasi lama. Mode web v0.4 mengganti aturan duduk, sudut berdiri dan target kemiringan dengan aturan pribadi. Jalur app.py lama tetap memakai aturan lama; jalankan api.py melalui Uvicorn untuk versi ini.
- Tidak perlu merombak database. Ekspor dan SQLite menyimpan personal_rules, personal_calibration, assessment_mode dan hasil tiap percobaan, termasuk acuan/toleransi/selisih.
- Hasil lama tetap ditampilkan sebagai aturan versi lama. Tidak dihitung ulang memakai aturan v0.4 karena belum memiliki kalibrasi pribadi lengkap.
- Gunakan posisi kamera dan kursi yang sama sesudah kalibrasi. Jika kamera/kursi berubah, akhiri sesi dan lakukan kalibrasi baru. Sistem belum otomatis mendeteksi perpindahan kamera.
- Angka tetap boleh disesuaikan untuk pengembangan berikutnya; catat versinya dan uji ulang agar perilaku serta data lama bisa ditelusuri.
