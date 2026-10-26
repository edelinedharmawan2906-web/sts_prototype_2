"""Optional local MQTT telemetry. HTTP and assessment remain authoritative."""
import json
import logging
import os
from threading import RLock
from time import monotonic
import paho.mqtt.client as mqtt
from serialization import json_scalar

log = logging.getLogger(__name__)


class MqttBridge:
    def __init__(self, enabled=None, host=None, port=None):
        self.enabled = (os.getenv('STS_MQTT_ENABLED', '0') == '1'
                        if enabled is None else enabled)
        self.host = host or os.getenv('STS_MQTT_HOST', '127.0.0.1')
        self.port = int(port or os.getenv('STS_MQTT_PORT', '1883'))
        self.topic = 'sts/latihan'
        self.client = None
        self.lock = RLock()
        self.last = {}
        self.last_error = None
        self.accepted = 0

    def start(self):
        if not self.enabled or self.client is not None:
            return
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.on_connect = self._on_connect
        client.on_connect_fail = self._on_connect_fail
        client.on_disconnect = self._on_disconnect
        client.reconnect_delay_set(min_delay=1, max_delay=10)
        self.client = client
        client.connect_async(self.host, self.port, 60)
        client.loop_start()

    def stop(self):
        if self.client is not None:
            self.client.disconnect()
            self.client.loop_stop()
            self.client = None

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        with self.lock:
            self.last_error = str(reason_code) if reason_code.is_failure else None
            self.last.clear()
        if not reason_code.is_failure:
            log.info('MQTT terhubung: %s:%s', self.host, self.port)

    def _on_connect_fail(self, client, userdata):
        with self.lock:
            self.last_error = 'Broker belum dapat dihubungi; mencoba lagi'

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            with self.lock:
                self.last_error = 'Koneksi broker terputus; mencoba lagi'

    def status(self):
        with self.lock:
            return dict(enabled=self.enabled,
                        connected=bool(self.client and self.client.is_connected()),
                        host=self.host, port=self.port, topic=self.topic,
                        last_error=self.last_error, queued_messages=self.accepted)

    def forget(self, sid):
        with self.lock:
            self.last.pop(sid, None)

    def send(self, sid, input_source, t, state, force=False):
        # No blocking connection or wait_for_publish inside the frame handler.
        # Live QoS 0: skip unavailable broker; do not retain old measurements.
        client = self.client
        if not self.enabled or client is None or not client.is_connected():
            return
        key = (state['mode'], state['phase'], state['complete'], state['cycles'],
               state['quality']['accepted'], state['closed'])
        now = monotonic()
        with self.lock:
            previous = self.last.get(sid)
            if not force and previous and previous[1] == key and now-previous[0] < .5:
                return
            m = state['measurement'] or {}
            payload = dict(schema_version=1, session_id=sid, input_source=input_source,
                           t=t, mode=state['mode'], phase=state['phase'],
                           knee_angle=m.get('knee'), hip_angle=m.get('hip'),
                           trunk_lean=m.get('lean'), complete=state['complete'],
                           cycles=state['cycles'], pose_valid=state['quality']['accepted'],
                           closed=state['closed'], message=state['message'])
            try:
                result = client.publish(self.topic, json.dumps(payload, default=json_scalar,
                                        allow_nan=False, ensure_ascii=False), qos=0, retain=False)
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    self.last[sid] = (now, key)
                    self.accepted += 1
                else:
                    self.last_error = mqtt.error_string(result.rc)
            except (OSError, ValueError, TypeError) as exc:
                self.last_error = str(exc)
                log.warning('MQTT pesan dilewati: %s', exc)
