# Perbaikan v0.4.1 — pemilihan cuplikan duduk awal

Video dan JSON sesi pengguna memperlihatkan posisi duduk teramati, tetapi v0.4 mengosongkan sebagian penilaian awal.

## Penyebab dan perubahan

- Mesin memakai waktu awal kondisi yang perlu bertahan 0,3 detik. Waktu itu lebih awal dari waktu keputusan.
- Catatan duduk terakhir dapat bertimestamp sedikit sesudah waktu awal tersebut. Pengecekan umur menjadi negatif, lalu bukti dianggap tidak tersedia.
- PersonalEngine sekarang menyimpan riwayat pendek cuplikan duduk dan memilih cuplikan terbaru yang benar-benar berada pada/sebelum waktu awal gerakan. Batas umur tetap 2 detik. Riwayat dibersihkan jika data terputus atau percobaan selesai.
- Pengambilan cuplikan kini menerima posisi lebih tegak daripada acuan duduk. Perbedaan yang melewati toleransi dinilai sebagai belum memenuhi, bukan dibuang sebagai tidak ada data. Pengumpulan tetap berhenti ketika kemiringan sudah masuk persiapan (lebih dari acuan +5°) agar tidak mengambil posisi sedang condong sebagai duduk awal.
- Tidak menggunakan nilai kalibrasi sebagai pengganti pengamatan yang hilang, tidak memakai sampel dari masa sesudah awal gerakan, dan tidak mengubah toleransi personal_rules.json.

## Hasil replay sesi yang dilaporkan

4 bangkit dan 3 siklus tetap terhitung.

| Percobaan | Hasil replay v0.4.1 |
| --- | --- |
| 1 | Memenuhi aturan asumsi; cuplikan duduk awal tersedia |
| 2 | Belum dapat dinilai keseluruhan; belum ada cuplikan duduk awal yang memenuhi syarat sebelum awal persiapan |
| 3 | Memenuhi aturan asumsi; cuplikan duduk awal tersedia |
| 4 | Belum memenuhi; berbeda dari acuan duduk dan tambahan kemiringan belum cukup |

Replay adalah pemeriksaan kode memakai pengukuran tersimpan. Hasil riwayat pengguna tidak diubah otomatis. Sesi lama tetap menyimpan hasil sebelumnya.

Untuk uji sesi baru: setelah kembali duduk, dekati posisi acuan duduk dan tahan diam sekitar 1 detik sebelum mulai condong lagi. Data yang belum memenuhi syarat pengamatan tetap ditampilkan sebagai belum dapat dinilai.

## Memperbarui

Hentikan backend lama, ekstrak ZIP baru ke STS_TA_Camera_v041. Untuk membawa riwayat, salin data dan results_api dari folder lama ke folder baru setelah server berhenti. Jalankan backend dari folder baru menggunakan Python/venv yang sudah berhasil, lalu refresh sampai label v0.4.1 terlihat. Rincian menjalankan ada di MULAI_V04.md; folder versi terbaru bernama STS_TA_Camera_v041.

## Pengujian

- Build TypeScript/Vite berhasil.
- python -m unittest test_api test_history test_personal test_snapshot -q: 23 tes.
- Regression replay memakai fixture pengukuran tanpa video/landmark, dengan acuan serta aturan sesi asli.
- Pemeriksaan waktu sebelum onset, penolakan cuplikan masa depan/kedaluwarsa, pembersihan saat data hilang, dan pengamatan postur lebih tegak diperiksa.
- Kamera fisik dan tampilan browser grafis perlu dicoba pada perangkat pengguna.
