"""Receive STS telemetry; run separately from Uvicorn."""
import json
import paho.mqtt.client as mqtt


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print(f'Koneksi gagal: {reason_code}', flush=True)
        return
    client.subscribe('sts/latihan')


def on_subscribe(client, userdata, mid, reason_codes, properties):
    if any(code.is_failure for code in reason_codes):
        print('Langganan ditolak broker.', flush=True)
    else:
        print('Siap menerima hasil STS pada sts/latihan', flush=True)


def on_message(client, userdata, message):
    text = message.payload.decode('utf-8', errors='replace')
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        print(f'{message.topic} | {text}', flush=True)
        return
    print(f'{message.topic} | {json.dumps(data, ensure_ascii=False)}', flush=True)


if __name__ == '__main__':
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_message = on_message
    try:
        client.connect('127.0.0.1', 1883, 60)
        client.loop_forever()
    except KeyboardInterrupt:
        print('\nPenerima dihentikan.')
    except OSError as exc:
        print(f'Broker belum tersedia: {exc}. Jalankan Mosquitto dahulu.')
        raise SystemExit(1)
    finally:
        client.disconnect()
