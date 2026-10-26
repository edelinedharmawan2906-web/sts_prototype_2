import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from engine import Config
from personal_engine import PersonalEngine
from personal_rules import PersonalRules, collect_personal, summarize
from fastapi.testclient import TestClient
import api
from demo_data import landmarks


def reference(hip=100,knee=90,lean=15,ankle=.25,y=310):
    m=dict(y=y,hip=hip,knee=knee,lean=lean,thigh=5,ankle=ankle)
    return summarize([(i*.05,m) for i in range(45)])

class PersonalTest(unittest.TestCase):
    def engine(self,lean=15):
        e=PersonalEngine(Config(),PersonalRules())
        e.set_references(reference(lean=lean),reference(hip=155,knee=155,lean=8,y=200))
        e.rise_threshold=.01
        return e
    def exercise(self,e,ankle=.25,peak=35,stand_angle=155,progress=1,return_seated=True):
        t=0
        def frames(n,p,lean,hip,knee):
            nonlocal t
            for i in range(n):
                x=i/(n-1) if n>1 else 0
                value=lambda v: v(x) if callable(v) else v
                e.update(t,value(p),value(lean),value(hip),value(knee),5,ankle)
                t+=.05
        frames(30,0,e.lean_base,100,90)
        frames(20,0,peak,100,90)
        frames(40,lambda x:x*progress,peak,lambda x:100+x*(stand_angle-100),lambda x:90+x*(stand_angle-90))
        frames(30,progress,8,stand_angle,stand_angle)
        if return_seated:
            frames(30,lambda x:progress*(1-x),e.lean_base,lambda x:stand_angle+(100-stand_angle)*x,lambda x:stand_angle+(90-stand_angle)*x)
            frames(30,0,e.lean_base,100,90)
        return e
    def test_personal_standing_below_165_is_counted(self):
        e=self.exercise(self.engine())
        self.assertEqual((e.complete,e.cycles),(1,1))
        r=e.results[0]
        self.assertEqual(r['status_sts'],'MEMENUHI')
        self.assertEqual(r['penilaian_tahap']['berdiri']['target_knee'],145)
        self.assertEqual(r['penilaian_tahap']['duduk']['pengukuran']['ankle']['acuan'],.25)
    def test_sitting_tolerance_boundaries(self):
        e=self.engine()
        self.assertTrue(e.sitting_matches(110,25,15,.35))
        self.assertFalse(e.sitting_matches(110.1,25,15,.35))
        self.assertFalse(e.sitting_matches(100,15,5,.351))
    def test_failed_posture_does_not_block_count(self):
        e=self.exercise(self.engine(),ankle=.37)
        self.assertEqual(e.complete,1)
        self.assertFalse(e.results[0]['duduk_awal_sesuai'])
        self.assertFalse(e.results[0]['penilaian_tahap']['duduk']['pengukuran']['ankle']['memenuhi'])
    def test_lean_uses_increment_not_absolute_angle(self):
        e=self.exercise(self.engine(lean=20),peak=28)
        self.assertEqual(e.complete,1)
        self.assertFalse(e.results[0]['penilaian_tahap']['condong']['memenuhi'])
        self.assertAlmostEqual(e.results[0]['penilaian_tahap']['condong']['tambahan_teramati'],8)
    def test_incomplete_and_low_height_not_counted(self):
        for angle,p in ((144,1),(155,.85)):
            e=self.exercise(self.engine(),stand_angle=angle,progress=p)
            self.assertEqual(e.complete,0)
            self.assertEqual(e.cycles,0)
            self.assertFalse(e.results[0]['bangkit_lengkap'])
    def test_gap_does_not_fabricate_confirmation(self):
        e=self.exercise(self.engine(),stand_angle=144,return_seated=False)
        e.missing();e.finish(10,False)
        self.assertIsNone(e.results[-1]['bangkit_lengkap'])
        self.assertIsNone(e.results[-1]['penilaian_tahap']['condong']['memenuhi'])
    def test_stable_calibration_and_gap(self):
        samples=[];r=PersonalRules();m=reference()['median']
        for i in range(45): done,_=collect_personal(samples,i*.05,m,480,r)
        self.assertTrue(done)
        done,_=collect_personal(samples,4,m,480,r)
        self.assertFalse(done);self.assertEqual(len(samples),1)
        samples=[]
        for i in range(45):
            done,_=collect_personal(samples,i*.05,{**m,'knee':90+(15 if i%2 else 0)},480,r)
        self.assertFalse(done)
    def test_custom_rules_are_used(self):
        r=PersonalRules(sitting_angle_tolerance=3,standing_angle_tolerance=5,lean_addition=15)
        e=PersonalEngine(Config(),r);e.set_references(reference(),reference(hip=155,knee=155,y=200))
        self.assertEqual(e.standing_targets(),(150,150))
        self.assertEqual(e.cfg.lean_min,30)
        self.assertFalse(e.sitting_matches(104,15,5,.25))

class PersonalApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.db=patch.object(api,'DB_PATH',Path(self.tmp.name)/'sessions.sqlite3');self.db.start()
        api.sessions.clear();self.client=TestClient(api.app);self.sid=self.client.post('/sessions',json={'input_source':'browser_camera'}).json()['session_id'];self.t=0
    def tearDown(self):
        (api.ROOT/'results_api'/(self.sid+'.json')).unlink(missing_ok=True)
        api.sessions.clear();self.db.stop();self.tmp.cleanup()
    def frames(self,m,n=55):
        with patch.object(api,'measure',return_value={**m,'hand':False}):
            for _ in range(n):
                r=self.client.post(f'/sessions/{self.sid}/frames',json={'t':self.t,'landmarks':landmarks()})
                self.assertEqual(r.status_code,200);self.t+=.05
        return r.json()
    def test_api_captures_personal_reference_and_persists(self):
        self.client.post(f'/sessions/{self.sid}/calibration',json={'posture':'duduk','delay':0})
        r=self.frames(reference()['median'])
        self.assertEqual(r['mode'],'CAL_BERDIRI')
        self.client.post(f'/sessions/{self.sid}/calibration',json={'posture':'berdiri','delay':0})
        r=self.frames(reference(hip=155,knee=155,y=200)['median'])
        self.assertEqual(r['mode'],'KEMBALI')
        self.assertEqual(r['personal_calibration']['berdiri']['median']['knee'],155)
        self.assertEqual(api.sessions[self.sid].engine.standing_targets(),(145,145))
        self.client.post(f'/sessions/{self.sid}/finish').raise_for_status()
        data=self.client.get(f'/sessions/{self.sid}/export').json()
        self.assertEqual(data['assessment_mode'],'personal_dummy_v1')
        self.assertEqual(data['personal_rules']['sitting_ankle_tolerance'],.1)
        api.sessions.clear()
        self.assertEqual(self.client.get(f'/history/{self.sid}').json()['data'],data)
    def test_invalid_standing_reference_keeps_capture_pending(self):
        self.client.post(f'/sessions/{self.sid}/calibration',json={'posture':'duduk','delay':0})
        self.frames(reference()['median'])
        self.client.post(f'/sessions/{self.sid}/calibration',json={'posture':'berdiri','delay':0})
        r=self.frames(reference(y=200)['median']) # height changes, but angles do not
        self.assertEqual(r['mode'],'CAL_BERDIRI')
        self.assertIsNotNone(r['capture'])
        self.assertIsNone(r['personal_calibration']['berdiri'])

if __name__=='__main__':unittest.main()
