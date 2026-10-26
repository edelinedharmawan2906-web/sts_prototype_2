# Versi terbaru v0.4.2

Gunakan folder STS_TA_Camera_v042 dan label v0.4.2. Baca PERBAIKAN_V042.md. Catatan versi sebelumnya di bawah bersifat historis.

# Versi terbaru v0.4.1

Gunakan folder STS_TA_Camera_v041, lalu pastikan label halaman v0.4.1. Baca PERBAIKAN_V041.md. Langkah menjalankan di bawah tetap berlaku.

# Mulai v0.4 — acuan pribadi

## Perbarui dari v0.3/v0.3.1

1. Hentikan backend dengan Ctrl+C.
2. Ekstrak STS_TA_Camera_v04.zip ke folder baru.
3. Untuk mempertahankan riwayat, salin folder data dan results_api dari folder aplikasi lama ke STS_TA_Camera_v04. Simpan folder lama sampai riwayat berhasil dibuka.
4. Jalankan backend dari folder STS_TA_Camera_v04 yang berisi api.py. Gunakan lingkungan Python yang sudah berhasil atau buat venv baru. Tidak perlu Node.js untuk mencoba.

HP/Linux dengan venv di folder proyek:

```bash
.venv-api/bin/python -m pip install -r requirements-api.txt
.venv-api/bin/python -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Jika venv belum ada, buat dengan python3 -m venv .venv-api. Jika venv ada di folder lama, panggil Python menggunakan alamat lengkapnya; alamat relatif .venv-api/bin/python hanya berlaku bila folder tersebut memang berada di proyek saat ini. Jika sebelumnya memakai Python tanpa venv dan sudah berhasil, gunakan python -m uvicorn api:app --host 127.0.0.1 --port 8000 seperti sebelumnya.

Windows:

```powershell
py -3.11 -m venv .venv-api
.\.venv-api\Scripts\python.exe -m pip install -r requirements-api.txt
.\.venv-api\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Gunakan -3.12 bila Python-mu versi 3.12.

## Coba

1. Buka http://127.0.0.1:8000 dan refresh sampai label v0.4 terlihat.
2. Aktifkan kamera. Rekam posisi duduk pribadi dengan hitung mundur; setelah waktunya habis, tahan diam minimal 2 detik.
3. Rekam posisi berdiri pribadi dengan cara yang sama. Sistem memeriksa stabilitas dan perbedaan dari duduk, bukan syarat harus 165°.
4. Kembali duduk selama 1 detik, lalu lakukan latihan.
5. Lihat Acuan pribadi sesi ini untuk nilai kalibrasi yang tersimpan.
6. Pada hasil, buka rincian posisi duduk serta syarat berdiri. Masing-masing menunjukkan acuan dan batas pribadi.
7. Akhiri & simpan, lalu buka riwayat. Sesi baru ditandai dengan aturan pribadi; sesi lama tetap menggunakan penilaian versi lama.

Tanpa kamera, buka http://127.0.0.1:8000/simulation dan jalankan simulasi 1 siklus; targetnya 1 bangkit dan 1 siklus. Simulasi memakai data titik tubuh buatan.

Baca ATURAN_KALIBRASI.md untuk seluruh aturan asumsi beserta contoh angka. Ubah personal_rules.json untuk menyesuaikan toleransi di sesi baru. Jangan mengubah angka di frontend: perhitungan tetap dilakukan Python.

## File baru

- personal_rules.json: nilai aturan yang mudah diedit.
- personal_rules.py: validasi pengaturan, pengumpulan sampel stabil, dan ringkasan kalibrasi.
- personal_engine.py: menggunakan mesin TA dengan pemeriksaan acuan pribadi.
- test_personal.py: uji perilaku acuan pribadi.

api.py menyimpan kalibrasi pribadi lengkap dan memilih PersonalEngine. engine.py menyediakan fungsi pemeriksaan yang dapat diganti oleh PersonalEngine; Engine lama tetap tersedia untuk regresi dan app.py. React menerima seluruh hasil dari Python.

## Uji kode

```bash
python -m unittest test_api test_history test_personal -v
python test_engine.py
```

Batas fase, tinggi, kecepatan dan toleransi dipilih untuk latihan teknis IIPP. Sistem tidak menyimpulkan pemulihan atau kelayakan postur secara klinis.
