# Verifikasi v0.5.0

- 27 tes API, riwayat, personal calibration dan snapshot: lulus.
- Regresi engine lama (python test_engine.py): lulus.
- TypeScript dan Vite build: lulus.
- Tes integrasi MQTT melalui socket TCP lokal menggunakan broker aMQTT: lulus. Satu siklus sintetis menghasilkan 1 bangkit dan 1 siklus; topic dan nilai sudut sesuai frame sumber; kehilangan pose menghasilkan sudut null; API tetap merespons saat broker dihentikan; koneksi dan publikasi pulih setelah broker dijalankan kembali; pesan closed=true dan riwayat SQLite tersedia setelah finish.

Pengujian dilakukan di Linux dengan broker aMQTT sebagai dependency khusus tes, bukan pengujian installer Mosquitto/PowerShell di Windows. Kamera fisik tidak diuji di lingkungan ini. Lakukan uji pengguna dengan Mosquitto dan kamera laptop menggunakan MULAI_MQTT.md. MQTT memakai QoS 0 untuk data langsung, sehingga tidak menjamin setiap pesan sampai; riwayat lengkap tetap melalui JSON/SQLite.

Tes MQTT opsional: instal requirements-test-mqtt.txt, lalu python -m unittest test_mqtt -v. Untuk aplikasi sehari-hari cukup requirements-api.txt.
