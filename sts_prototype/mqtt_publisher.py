import json
import paho.mqtt.publish as publish

# Data contoh latihan, belum berasal dari kamera.
data = {
    "session_id": "latihan01",
    "phase": "BERDIRI",
    "knee_angle": 170,
    "complete": 1
}

publish.single(
    topic="sts/latihan",
    payload=json.dumps(data),
    hostname="127.0.0.1",
    port=1883
)

print("Data terkirim:", data)