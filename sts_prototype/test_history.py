"""Persistence, API integration and duplicate-save regression checks."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import api
from demo_data import run_demo

class HistoryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(api, 'DB_PATH', Path(self.temp.name)/'sts.sqlite3')
        self.db_patch.start()
        self.client = TestClient(api.app)
        api.sessions.clear()
        self.ids = []
    def tearDown(self):
        for sid in self.ids:
            (api.ROOT/'results_api'/(sid+'.json')).unlink(missing_ok=True)
        api.sessions.clear()
        self.db_patch.stop()
        self.temp.cleanup()
    def test_saved_history_survives_restart(self):
        sid, result = run_demo(self.client)
        self.ids.append(sid)
        self.assertEqual(self.client.get('/history').json()['total'], 0)
        for _ in range(2):
            self.assertEqual(self.client.post(f'/sessions/{sid}/finish').status_code, 200)
        original = self.client.get(f'/sessions/{sid}/export').json()
        api.sessions.clear() # same loss of active session state as a server restart
        restarted = TestClient(api.app)
        history = restarted.get('/history').json()
        self.assertEqual(history['total'], 1)
        self.assertEqual(history['items'][0]['complete'], 1)
        self.assertEqual(history['items'][0]['cycles'], 1)
        detail = restarted.get(f'/history/{sid}').json()
        self.assertEqual(detail['data'], original)
        self.assertGreater(len(detail['data']['frames']), 300)
    def test_empty_unknown_and_pagination(self):
        self.assertEqual(self.client.get('/history').json()['items'], [])
        self.assertEqual(self.client.get('/history/unknown').status_code, 404)
        self.assertEqual(self.client.get('/history?limit=0').status_code, 422)
        for _ in range(3):
            sid = self.client.post('/sessions', json={}).json()['session_id']
            self.ids.append(sid)
            self.client.post(f'/sessions/{sid}/finish')
        first = self.client.get('/history?limit=2').json()
        second = self.client.get('/history?limit=2&offset=2').json()
        self.assertEqual(first['total'], 3)
        self.assertEqual(len(first['items']), 2)
        self.assertEqual(len(second['items']), 1)
        self.assertNotIn(second['items'][0]['id'], [v['id'] for v in first['items']])
    def test_retry_after_database_error(self):
        sid = self.client.post('/sessions', json={}).json()['session_id']
        self.ids.append(sid)
        with patch.object(api, 'save_session', side_effect=OSError('disk error')):
            with self.assertRaises(OSError): self.client.post(f'/sessions/{sid}/finish')
        self.assertFalse(api.sessions[sid].closed)
        self.assertEqual(self.client.post(f'/sessions/{sid}/finish').status_code, 200)
        self.assertEqual(self.client.get('/history').json()['total'], 1)

if __name__ == '__main__': unittest.main()
