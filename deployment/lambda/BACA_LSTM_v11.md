# Lambda v11: geometri STS + LSTM sebagai pembanding

Unggah ZIP ini ke fungsi yang SUDAH ADA: `sts-api`. Runtime Python 3.12, x86_64, memory 512 MB, timeout 15 detik. Handler `lambda_function.lambda_handler`.

Tambahkan environment variable `STS_LSTM_ENABLED=1`. Pertahankan semua environment variable lain. Tidak memerlukan perubahan IAM, tabel, API Gateway, Cognito, atau role monitor. Tidak memanggil fungsi `sts-lstm-test`; model yang sama sekarang dibundel langsung dalam `sts-api` untuk menghindari pemanggilan Lambda tambahan.

Test console privat:

```json
{"action":"lstm_test"}
```

Harus mengembalikan `status: ok`, `sample_count: 9`, `enabled: true`, `used_for_sts_counts: false`, dengan selisih terhadap hasil TFLite Colab maksimum <=0.01. Test ini membaca fixture lokal paket; tidak menulis sesi ke DynamoDB. Ini tes kesetaraan prediksi, bukan MAE.

## Pemrosesan input

- Timestamp tetap berasal dari saat gambar kamera diambil, satuan detik. Waktu kedatangan HTTP tidak digunakan untuk membentuk window.
- Input raw sesuai urutan fitur yang disimpan: 33 landmark, masing-masing x/y/z/visibility; tidak dipindah, dinormalisasi ukuran tubuh, atau dikalibrasi pribadi sebelum scaler model. Koordinat x/y tetap ternormalisasi MediaPipe, bukan piksel. Geometri pembanding memakai ukuran piksel agar rasio aspek benar.
- Buffer disimpan per sesi dalam atribut `lstm_state` di STATE DynamoDB, terpisah dari checkpoint engine STS; tidak memakai buffer global Lambda. Hanya interpreter/statistik scaler yang digunakan ulang, tanpa recurrent state antar-panggilan.
- Grid model: 30 sampel berjarak 1/30 detik; rentangnya 29/30 detik (sekitar 1 detik), berakhir pada frame terbaru. Interpolasi linear hanya di dalam pengamatan yang tersedia; tanpa extrapolation.
- Asumsi teknis: minimal 10 pengamatan dalam buffer, jeda antar-frame maksimal 0.2 detik, inferensi paling sering setiap 0.2 detik waktu capture. Buffer dibatasi 64 frame dan dipangkas setelah window lama tidak diperlukan.
- Saat pose kiri gagal pemeriksaan kualitas geometri, buffer direset dan nilai lama dihapus. Jeda >0.2 detik juga mengulang pengumpulan. Interpolasi tidak memperbaiki frame/titik tubuh yang hilang atau membuat informasi gerakan baru.
- Prediksi lutut suatu sisi hanya ditampilkan jika pinggul/lutut/pergelangan kaki sisi itu memiliki visibility >=0.65 di seluruh window. Kanan dapat kosong ketika kamera berada di samping kiri. Semua ambang ini asumsi prototipe, belum validasi klinis.
- Inferensi tidak mengubah sudut engine, fase, kalibrasi, complete, cycles, atau attempts. Jika inferensi gagal, tampil `inference_error` dan jalur geometri tetap menyimpan hasilnya.

## Penyimpanan dan transport

State tambahan + history + receipt retry tetap masuk transaksi DynamoDB yang sama. Request/version yang sama menggunakan receipt lama tanpa mengulang analisis. Buffer tidak dikirim ke frontend. Data mentah history menyertakan `frame.lstm` dengan waktu, sudut pembanding, dan 39 output model ketika ready. Output ini mencakup koordinat sudut DAN translasi, bukan 39 sudut.

Endpoint `angles` dan pesan MQTT hanya membawa proyeksi kecil LSTM untuk grafik/kartu (tidak membawa 39 output lengkap). Export JSON lengkap tetap membawa semua hasil dan landmark. MQTT tetap best-effort setelah commit, versi/deduplikasi dan kebijakan akses pemilik tetap sama. Pembaruan tampilan mengikuti kumpulan frame, bukan jaminan setiap frame tampil langsung.

Ke-15 file yang membentuk sidik kode checkpoint STS dipertahankan persis seperti v10. Sesi lama dapat dibuka tanpa data LSTM dan dapat mulai mengisi buffer ketika frame baru masuk. Untuk pengujian lapangan, buat sesi baru agar riwayat perbandingan lengkap sejak awal.

## Runtime

Base dependency v10 dipertahankan (termasuk numpy 2.2.6). Tambahan LiteRT 2.3.0, wheel CPython 3.12 Linux x86_64 manylinux_2_27. Hanya subset CPU Interpreter yang dibundel: __init__, interpreter, metrics_portable, metrics_interface, _pywrap_litert_interpreter_wrapper.so, libpywrap_litert_common.so, libLiteRt.so. Metadata dan lisensi upstream tetap disertakan. Converter, GPU/NPU, tools, dan CompiledModel API tidak dibundel.

Model quantized SHA256: `53ff0976f8233fabfb614c9689d0b340c47490a6317735dedb10629a6aac208a`.

Lokal: 46 tes backend (termasuk replay, pemilik berbeda, state antar-batch/sesi, failure isolation, proyeksi MQTT/grafik/export, kesetaraan model). Artefak ZIP diekstrak ulang dan diuji dengan Python 3.12 tanpa site-packages host. Belum menjalankan rilis v11 ini di AWS atau kamera pengguna; uji tersebut dilakukan setelah upload. Fungsi uji LSTM sebelumnya sudah berhasil di AWS, tetapi itu paket yang berbeda.

Rollback fitur: ubah `STS_LSTM_ENABLED=0`; kartu dan hasil tambahan menjadi disabled dan geometri tetap berjalan. Jika perlu rollback kode, unggah kembali ZIP Lambda v10 yang sebelumnya digunakan. Jangan menghapus sesi atau tabel untuk melakukan rollback.
