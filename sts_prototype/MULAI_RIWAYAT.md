# Catatan v0.4

Dokumen berikut adalah panduan versi lama. Untuk menjalankan web terbaru dan aturan pribadi, gunakan **MULAI_V04.md** dan **ATURAN_KALIBRASI.md**.

# Pembaruan tampilan hasil v0.3.1

Status berdiri dipisahkan dari pemeriksaan postur, baik pada hasil terbaru maupun detail riwayat:

- Berdiri lengkap / berdiri lengkap belum tercapai / berdiri belum dapat dikonfirmasi.
- Duduk awal: hasil aturan dan alasan spesifik (misalnya posisi kaki awal melewati batas prototipe).
- Condong saat persiapan: hasil aturan, puncak teramati dan batas minimum.
- Buka Lihat nilai dan batas posisi duduk untuk rincian angka.

Aturan, ambang, hitungan, database, dan data JSON tidak diubah. Field status_sts pada JSON tetap tersedia seperti versi sebelumnya. Versi API dalam JSON tetap api0.3 karena perubahannya di antarmuka.

## Memperbarui dari v0.3 tanpa kehilangan riwayat

1. Hentikan backend lama dengan Ctrl+C.
2. Ekstrak ZIP ke folder STS_TA_Camera_v031.
3. Salin folder data dan results_api dari folder aplikasi v0.3 yang sebelumnya kamu jalankan ke folder baru ini. Jangan hapus folder lama sebelum riwayat berhasil dibuka di versi baru.
4. Jalankan backend dari folder baru menggunakan lingkungan Python yang sudah berhasil. Venv lama dapat dipakai melalui alamat Python lengkap; jika membuat venv baru, pasang requirements-api.txt dahulu.
5. Buka http://127.0.0.1:8000, refresh halaman sampai label v0.3.1 terlihat, lalu buka riwayat dan pilih sesi.

Riwayat v0.3 dapat ditampilkan dengan format baru tanpa merekam ulang. Panduan menjalankan pada HP dan Windows ada di bawah. Node.js tidak diperlukan untuk mencoba paket ini.

---

# STS TA Kamera v0.3.1 — hasil berdiri dan pemeriksaan postur

Versi ini melanjutkan v0.2: kamera, MediaPipe, pengukuran, serta engine TA tetap dipakai. Tambahannya adalah penyimpanan SQLite dan panel Riwayat latihan pada halaman kamera.

## Jalankan di HP (terminal Linux/Termux yang sebelumnya berhasil)

1. Hentikan backend lama dengan Ctrl+C.
2. Ekstrak ZIP ini ke folder baru. Buka terminal di dalam folder STS_TA_Camera_v031 yang berisi api.py. Acode dapat dipakai mengedit folder ini seperti sebelumnya; server tetap dijalankan dari terminal.
3. Gunakan Python/lingkungan Python yang sebelumnya berhasil. Jika memakai venv, aktifkan dahulu. Jalankan:

```bash
python -m pip install -r requirements-api.txt
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Jika perintah Python di lingkunganmu bernama python3, ganti python menjadi python3. Jika instalasi meminta memakai virtual environment, gunakan lingkungan virtual yang sebelumnya sudah berhasil; jangan memaksa instalasi ke Python sistem.

4. Biarkan terminal berjalan. Buka http://127.0.0.1:8000 di browser HP yang sama. Pastikan label halaman menunjukkan v0.3.1.

## Jalankan di Windows

Buka terminal pada folder hasil ekstrak yang berisi api.py. Hentikan server lama dahulu.

```powershell
py -3.11 -m venv .venv-api
.\.venv-api\Scripts\python.exe -m pip install -r requirements-api.txt
.\.venv-api\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Jika memakai Python 3.12, ganti -3.11 menjadi -3.12. Buka http://127.0.0.1:8000. Node.js tidak diperlukan untuk mencoba karena frontend sudah dibangun.

## Uji satu fitur baru

1. Jalankan kamera, rekam duduk, rekam berdiri, kembali duduk, lalu lakukan latihan seperti v0.2.
2. Tekan Akhiri & simpan.
3. Gulir ke panel Riwayat latihan, tekan Buka riwayat latihan atau Perbarui riwayat.
4. Pilih sesi. Lihat waktu penyimpanan, hitungan, durasi dan hasil tiap percobaan. Tombol unduh menyediakan ekspor lengkap termasuk landmark.
5. Hentikan backend dengan Ctrl+C.
6. Jalankan backend lagi dari folder yang sama, refresh browser, lalu buka riwayat. Sesi tadi tetap tersedia tanpa menyalakan kamera.

Tanpa kamera, buka /simulation, jalankan simulasi sampai tersimpan, lalu kembali ke /camera/ dan buka riwayat. Sesi ditandai Simulasi.

## Apa yang disimpan?

- data/sts.sqlite3: database SQLite. Dibuat otomatis ketika riwayat diakses atau sesi disimpan. SQLite sudah termasuk dalam Python; tidak perlu memasang server database.
- results_api/{id}.json: salinan ekspor seperti sebelumnya.
- Riwayat menyimpan ID, waktu penyimpanan UTC, sumber input, hitungan, jumlah percobaan dan ekspor lengkap. Browser menampilkan waktu sesuai zona waktu perangkat.
- Database menyimpan data landmark, bukan video kamera.
- Riwayat baru memuat sesi yang disimpan dengan v0.3. JSON dari versi lama belum otomatis diimpor.
- Cadangkan folder data dan results_api setelah backend dihentikan. Saat pindah versi/folder, salin keduanya ke folder aplikasi yang baru sebelum menjalankan server. Jika folder data dihapus, riwayat database ikut hilang.
- Penyimpanan masih lokal di perangkat yang menjalankan Python; belum cloud, akun pengguna, atau sinkronisasi antarperangkat.

## Pelajari kode mengikuti satu tombol

Akhiri & simpan → main.tsx: finish() → sts-client.ts: finish() → api.py: finish() → database.py: save_session().

Buka riwayat → History.tsx: refresh() → sts-client.ts: history() → GET /history → database.py: list_sessions().

Pilih sesi → History.tsx: open() → sts-client.ts: detail() → GET /history/{id} → database.py: load_session().

Endpoint riwayat membaca SQLite, sehingga tidak bergantung pada dictionary sessions di RAM. Daftar dibaca 50 sesi per halaman; detail lengkap hanya diambil saat sesi dipilih. Menyimpan ulang ID yang sama tidak membuat baris ganda.

## Jika mengedit frontend

Kode ada di frontend/src. Setelah mengubahnya, jalankan npm ci lalu npm run build dari folder frontend; refresh browser. Menyunting src tanpa membangun ulang belum mengubah halaman yang disajikan FastAPI.

## Verifikasi mandiri

```bash
python -m unittest test_api test_history -v
python test_engine.py
```

Tes database menggunakan folder sementara, sehingga tidak menambahkan data pengujian ke riwayatmu.
