"""Real MQTT socket integration test; optional dependency: amqtt>=0.11,<0.12."""
import asyncio
import json
import socket
import tempfile
import time
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch
import paho.mqtt.client as mqtt
from amqtt.broker import Broker
from fastapi.testclient import TestClient
import api
from demo_data import run_demo, landmarks
from mqtt_bridge import MqttBridge


def wait_until(predicate, seconds=10):
    deadline = time.monotonic()+seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.02)
    raise AssertionError('Timed out waiting for MQTT condition')


class MqttIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_results_outage_and_recovery(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]

        def make_broker():
            return Broker({'listeners': {'default': {'type': 'tcp', 'bind': f'127.0.0.1:{port}'}},
                           'plugins': {'amqtt.plugins.authentication.AnonymousAuthPlugin':
                                       {'allow_anonymous': True}}})

        bridge = MqttBridge(enabled=True, port=port)
        received = []
        subscribed = Event()
        subscriber = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        subscriber.reconnect_delay_set(1, 2)
        subscriber.on_connect = lambda c, u, f, r, p: c.subscribe('sts/latihan')
        subscriber.on_subscribe = lambda c, u, m, r, p: subscribed.set()
        subscriber.on_message = lambda c, u, m: received.append(json.loads(m.payload))
        broker = make_broker()
        await broker.start()
        api.sessions.clear()
        temp = tempfile.TemporaryDirectory()
        db_patch = patch.object(api, 'DB_PATH', Path(temp.name)/'sts.sqlite3')
        bridge_patch = patch.object(api, 'mqtt_bridge', bridge)
        db_patch.start(); bridge_patch.start()
        client = None
        sid = None
        try:
            subscriber.connect_async('127.0.0.1', port)
            subscriber.loop_start()
            await asyncio.to_thread(wait_until, subscribed.is_set)

            def exercise():
                nonlocal client, sid
                client = TestClient(api.app)
                client.__enter__()
                wait_until(lambda: bridge.status()['connected'])
                sid, result = run_demo(client)
                self.assertEqual(result['complete'], 1)
                self.assertEqual(result['cycles'], 1)
                wait_until(lambda: any(m['session_id'] == sid and m['cycles'] == 1 for m in received))
                telemetry = [m for m in received if m['session_id'] == sid][-1]
                self.assertEqual(telemetry['phase'], result['phase'])
                # MQTT samples frames, so compare against the matching timestamp.
                row = next(row for row in api.sessions[sid].rows if row['t'] == telemetry['t'])
                self.assertAlmostEqual(telemetry['knee_angle'], row['measurement']['knee'])
                self.assertEqual(telemetry['input_source'], 'simulation')
                self.assertNotIn('landmarks', telemetry)
                return api.sessions[sid].last_t

            t = await asyncio.to_thread(exercise)
            subscribed.clear()
            await broker.shutdown()
            await asyncio.to_thread(wait_until, lambda: not bridge.status()['connected'])

            def offline():
                r = client.post(f'/sessions/{sid}/frames', json={'t': t+.05, 'landmarks': None})
                self.assertEqual(r.status_code, 200)
                self.assertIsNone(r.json()['measurement'])
                self.assertEqual(r.json()['complete'], 1)
                self.assertEqual(client.get('/health').status_code, 200)
                self.assertFalse(client.get('/health').json()['mqtt']['connected'])

            await asyncio.to_thread(offline)
            broker = make_broker()
            await broker.start()
            await asyncio.to_thread(wait_until, lambda: bridge.status()['connected'] and subscribed.is_set())

            def finish():
                r = client.post(f'/sessions/{sid}/frames', json={'t': t+.1, 'landmarks': None})
                self.assertEqual(r.status_code, 200)
                wait_until(lambda: any(m['session_id'] == sid and m['t'] == t+.1 for m in received))
                m = [m for m in received if m['session_id'] == sid][-1]
                self.assertIsNone(m['knee_angle'])
                self.assertFalse(m['pose_valid'])
                self.assertEqual(client.post(f'/sessions/{sid}/finish').status_code, 200)
                wait_until(lambda: any(m['session_id'] == sid and m['closed'] for m in received))
                self.assertEqual(client.get(f'/history/{sid}').status_code, 200)

            await asyncio.to_thread(finish)
        finally:
            if client is not None:
                await asyncio.to_thread(client.__exit__, None, None, None)
            subscriber.disconnect()
            await asyncio.to_thread(subscriber.loop_stop)
            await broker.shutdown()
            db_patch.stop(); bridge_patch.stop()
            if sid:
                (api.ROOT/'results_api'/(sid+'.json')).unlink(missing_ok=True)
            api.sessions.clear()
            temp.cleanup()


if __name__ == '__main__':
    unittest.main()
