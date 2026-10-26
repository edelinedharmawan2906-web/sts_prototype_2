import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import api
from fastapi.testclient import TestClient
from api import app,sessions,ROOT
from demo_data import run_demo,landmarks

class ApiTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db_patch=patch.object(api,'DB_PATH',Path(self.temp.name)/'test.sqlite3');self.db_patch.start()
        sessions.clear();self.client=TestClient(app)
    def tearDown(self):
        for sid in list(sessions):
            (ROOT/'results_api'/(sid+'.json')).unlink(missing_ok=True)
        sessions.clear()
        self.db_patch.stop();self.temp.cleanup()
    def test_end_to_end(self):
        sid,result=run_demo(self.client)
        self.assertEqual(result['complete'],1);self.assertEqual(result['cycles'],1)
        self.assertEqual(result['mode'],'LATIHAN')
        second=self.client.post('/sessions',json={}).json()['session_id']
        self.assertEqual(self.client.get('/sessions/'+second).json()['complete'],0)
        self.assertEqual(self.client.post('/sessions/'+sid+'/finish').status_code,200)
        self.assertTrue((ROOT/'results_api'/(sid+'.json')).exists())
        self.assertEqual(self.client.post('/sessions/'+sid+'/frames',json={'t':99}).status_code,409)
        data=self.client.get('/sessions/'+sid+'/export').json()
        self.assertEqual(data['angle_source'],'geometry_2d');self.assertGreater(len(data['frames']),300)
    def test_validation_and_missing(self):
        sid=self.client.post('/sessions',json={}).json()['session_id'];url='/sessions/'+sid
        self.assertEqual(self.client.post(url+'/calibration',json={'posture':'berdiri'}).status_code,409)
        self.client.post(url+'/calibration',json={'posture':'duduk','delay':10})
        for t in (0,1,2):
            self.assertEqual(self.client.post(url+'/frames',json={'t':t,'landmarks':None}).status_code,200)
        self.assertEqual(sessions[sid].pending['deadline'],10)
        self.assertEqual(self.client.post(url+'/frames',json={'t':2}).status_code,409)
        self.assertEqual(self.client.post(url+'/frames',json={'t':3,'landmarks':[]}).status_code,422)
        low=landmarks();low[23]['visibility']=.1
        self.assertIsNone(self.client.post(url+'/frames',json={'t':3,'landmarks':low}).json()['measurement'])
        self.assertEqual(self.client.get('/sessions/no-such-id').status_code,404)
    def test_geometry(self):
        from measurements import measure
        from types import SimpleNamespace as NS
        m=measure(NS(pose_landmarks=NS(landmark=[NS(**v) for v in landmarks()])),640,480)
        self.assertAlmostEqual(m['hip'],90);self.assertAlmostEqual(m['knee'],90)
        self.assertAlmostEqual(m['lean'],0)

    def test_countdown_without_visible_body(self):
        sid=self.client.post('/sessions',json={'input_source':'browser_camera'}).json()['session_id']
        url='/sessions/'+sid
        r=self.client.post(url+'/calibration',json={'posture':'duduk','delay':10})
        self.assertEqual(r.status_code,200)
        for t in (0,3,10,11):
            r=self.client.post(url+'/frames',json={'t':t,'landmarks':None}).json()
        self.assertEqual(r['capture']['remaining_seconds'],0)
        self.assertTrue(r['capture']['recording'])
        self.assertFalse(r['quality']['accepted'])
        self.assertEqual(r['calibration_samples'],0)
        for i in range(55):
            r=self.client.post(url+'/frames',json={'t':11.1+i*.05,'landmarks':landmarks()}).json()
        self.assertEqual(r['mode'],'CAL_BERDIRI')
        self.assertIsNone(r['capture'])
        self.assertEqual(self.client.get(url+'/export').json()['input_source'],'browser_camera')

    def test_routes_and_assets(self):
        r=self.client.get('/')
        self.assertEqual(r.status_code,200)
        self.assertIn('Gerak STS',r.text)
        self.assertEqual(self.client.get('/simulation').status_code,200)
        self.assertEqual(self.client.get('/camera/mediapipe/pose_landmarker_full.task').status_code,200)
        import re
        paths=re.findall(r'(?:src|href)="(/camera/assets/[^" ]+)"',r.text)
        self.assertTrue(paths)
        for path in paths:self.assertEqual(self.client.get(path).status_code,200)

    def test_closed_session_rejects_capture(self):
        sid=self.client.post('/sessions',json={}).json()['session_id']
        self.client.post('/sessions/'+sid+'/finish')
        self.assertEqual(self.client.post('/sessions/'+sid+'/calibration',json={'posture':'duduk'}).status_code,409)

if __name__=='__main__':unittest.main()
