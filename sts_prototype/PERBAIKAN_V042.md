# v0.4.2 — pisahkan pengumpulan data dari penilaian

Pada sesi d847..., v0.4.1 menghitung 4 bangkit dan 3 siklus, tetapi tidak menyimpan cuplikan duduk awal yang bisa dinilai. Pengambilan masih terikat batas kemiringan. Perbaikan ini mengganti pengambilan cuplikan berdasarkan kestabilan pinggul serta perubahan postur, tanpa batas sudut absolut terhadap kalibrasi.

PersonalEngine memakai kolektor sendiri dengan jendela sekitar 0,5 detik. Cuplikan awal yang teramati dibekukan selama persiapan. Jika awal persiapan belum tersedia, pengumpulan boleh berlanjut saat posisi masih rendah; bukti yang dipakai harus berada sebelum awal kenaikan pinggul. Angka penilaian tidak dilonggarkan. Aturan dan versi pengambilan dicatat dalam ekspor.

## Hasil replay JSON terbaru

| Percobaan | Hasil |
| --- | --- |
| 1 | Memenuhi aturan asumsi |
| 2 | Belum memenuhi; kemiringan duduk berbeda dari acuan |
| 3 | Belum memenuhi; kemiringan dan sudut badan–paha duduk berbeda dari acuan |
| 4 | Belum memenuhi; kemiringan duduk berbeda dari acuan |

Keempatnya memiliki data duduk awal; hitungan tetap 4 bangkit dan 3 siklus. Replay memeriksa kode menggunakan pengukuran yang tersimpan. Tidak mengubah hasil riwayat pengguna secara otomatis.

## Jalankan pembaruan

Hentikan backend lama (Ctrl+C). Ekstrak ZIP ke STS_TA_Camera_v042. Jika ingin mempertahankan riwayat, salin data dan results_api dari folder lama setelah backend berhenti. Jalankan backend dari folder baru dengan Python/venv yang sebelumnya berhasil. Refresh web sampai label v0.4.2 terlihat, lalu rekam sesi baru.

Perintah Windows jika .venv-api tersedia pada folder proyek:

```powershell
.\.venv-api\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Venv yang berada di folder lain dapat dipakai melalui alamat lengkap Python-nya. MULAI_V04.md memuat langkah instalasi lingkungan bila diperlukan.

Untuk mencoba, tahan duduk sejenak sebelum bangkit. Bila titik hilang atau tidak ada jendela stabil sebelum kenaikan, status belum dapat dinilai tetap mungkin muncul.

## Pengujian

Build dan 27 tes API/riwayat/aturan/pengambilan cuplikan lulus. Tes regresi Engine lama lulus. Dua fixture sesi nyata diputar ulang, tanpa video atau landmark dalam fixture. Tes mencakup postur condong yang stabil tetap dikumpulkan, perubahan sudut cepat ditolak, cuplikan awal tidak digantikan postur persiapan, data hilang, serta waktu data sebelum kenaikan pinggul. Kamera fisik dan tampilan browser grafis perlu diuji di perangkat pengguna.
