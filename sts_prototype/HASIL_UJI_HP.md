# Verifikasi v0.7.0

- 28 pengujian API, kalibrasi, snapshot, riwayat dan MQTT TCP: lulus.
- TypeScript dan Vite production build: lulus.
- Pengujian komponen React/jsdom memastikan URL broker memakai hostname alamat halaman (alamat IP berbeda dari 127.0.0.1).
- Pesan simulasi FastAPI melalui broker aMQTT dan MQTT.js WebSocket mencapai DOM: 1 bangkit, 1 siklus, sudut lutut 90.0 derajat, sumber Simulasi dan status Sesi selesai. Seleksi sesi, payload invalid, batas pesan, dan Putuskan juga diperiksa.

Batas pengujian: lingkungan Linux ini tidak memiliki rute ke alamat jaringan non-loopback sendiri (Network is unreachable). Dalam pengujian DOM, alamat broker yang diminta diperiksa dahulu, lalu koneksi tes diarahkan ke loopback untuk memeriksa pengiriman WebSocket nyata. Ini bukan pengujian dua perangkat di Wi-Fi. Kamera fisik, browser HP, Windows Firewall dan konfigurasi Mosquitto Windows perlu diuji pengguna sesuai MULAI_HP.md. jsdom bukan pengujian tampilan browser grafis. QoS 0 tidak menjamin setiap pesan sampai.
