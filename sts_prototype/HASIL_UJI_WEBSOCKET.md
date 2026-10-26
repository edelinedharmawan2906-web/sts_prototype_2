# Verifikasi v0.6.0

- 28 tes API/kalibrasi/snapshot/riwayat/MQTT TCP: lulus.
- TypeScript dan Vite production build: lulus. Pemantau dimuat terpisah sehingga bundle MQTT tidak dimuat saat hanya memakai kamera.
- Pengujian komponen React melalui jsdom dengan MQTT.js browser bundle dan sambungan WebSocket nyata ke broker aMQTT: lulus. Backend FastAPI menjalankan simulasi satu siklus, menerbitkan hasil melalui TCP, lalu broker meneruskan ke MQTT.js melalui WebSocket. DOM menampilkan 1 bangkit, 1 siklus, lutut 90.0 derajat, sumber Simulasi, dan Sesi selesai. Seleksi sesi, batas 30 baris, pengabaian payload manual berbeda format, dan tombol Putuskan juga diperiksa.

Lingkungan pengujian Linux. jsdom bukan browser grafis; tampilan visual dan kamera fisik tidak diuji. Installer/config Mosquitto Windows perlu diuji pengguna mengikuti MULAI_WEBSOCKET.md. Log broker uji aMQTT memunculkan diagnostic saat sambungan WebSocket ditutup paksa oleh tombol Putuskan; pemeriksaan data dan DOM tetap lulus. QoS 0 tanpa retain tetap tidak menjamin semua pesan diterima.
