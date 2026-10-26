import json
import unittest
from pathlib import Path
from engine import Config
from personal_engine import PersonalEngine
from personal_rules import PersonalRules
from test_personal import reference

class SnapshotTest(unittest.TestCase):
    def engine(self):
        e=PersonalEngine(Config(),PersonalRules())
        e.set_references(reference(),reference(hip=155,knee=155,y=200))
        return e
    def row(self,t,hip=100):
        return dict(time=t,passed=True,source='test',measurement=dict(hip=hip,lean=15,thigh=5,ankle=.25))
    def test_backdated_start_uses_earlier_observation(self):
        e=self.engine()
        e.seated_snapshots.extend([self.row(9.9),self.row(10.1,105)])
        e.last_sitting_t=10.1;e.last_sitting=True;e.sitting_details=self.row(10.1,105)['measurement']
        e.begin_attempt(10,30,False,'PERSIAPAN')
        self.assertTrue(e.initial_sitting)
        self.assertEqual(e.initial_sitting_t,9.9)
        self.assertEqual(e.initial_sitting_details['hip'],100)
    def test_future_and_stale_observations_not_substituted(self):
        e=self.engine();e.seated_snapshots.extend([self.row(5),self.row(10.1)])
        e.begin_attempt(10,30,False,'PERSIAPAN')
        self.assertIsNone(e.initial_sitting)
    def test_more_upright_posture_is_observed_then_scored(self):
        e=self.engine()
        for i in range(35): e.update(i*.05,0,0,100,90,5,.25)
        self.assertTrue(e.seated_snapshots)
        self.assertFalse(e.last_sitting) # differs by 15 degrees, but still observed
        self.assertIsNotNone(e.last_sitting_t)
        e.missing();self.assertFalse(e.seated_snapshots)
    def test_bent_stationary_posture_is_collected_and_scored(self):
        e=self.engine()
        for i in range(35):e.update(i*.05,0,32,100,90,5,.25)
        self.assertTrue(e.seated_snapshots)
        self.assertIsNotNone(e.initial_sitting)
        self.assertFalse(e.initial_sitting)
    def test_changing_angles_do_not_form_stable_posture(self):
        e=self.engine()
        for i in range(35):e.update(i*.05,0,0 if i%2 else 30,100,90,5,.25)
        self.assertFalse(e.seated_snapshots)
    def test_first_observed_origin_is_preserved_through_preparation(self):
        e=self.engine()
        for i in range(35):e.update(i*.05,0,15,100,90,5,.25)
        e.begin_attempt(1.7,30,False,'PERSIAPAN')
        saved=dict(e.initial_sitting_details)
        for i in range(35,90):e.update(i*.05,0,35,80,90,5,.25)
        self.assertEqual(e.initial_sitting_details,saved)
        self.assertTrue(e.initial_sitting)
    def test_latest_uploaded_session_has_observed_sitting(self):
        p=json.loads(Path('personal_latest_regression.json').read_text())
        e=PersonalEngine(Config(**p['config']),PersonalRules(**p['personal_rules']))
        e.set_references(p['personal_calibration']['duduk'],p['personal_calibration']['berdiri'])
        e.rise_threshold=p['calibration']['rise_threshold']
        for row in p['frames']:
            m=row['measurement']
            if m is None:e.missing();continue
            progress=(p['calibration']['seated_y']-m['y'])/(p['calibration']['seated_y']-p['calibration']['standing_y'])
            e.update(row['t'],progress,m['lean'],m['hip'],m['knee'],m['thigh'],m['ankle'])
        self.assertEqual((e.complete,e.cycles),(4,3))
        self.assertEqual([a['status_sts'] for a in e.results],['MEMENUHI']+['BELUM MEMENUHI']*3)
        for a in e.results:
            self.assertIsNotNone(a['duduk_awal_sesuai'])
            self.assertLessEqual(a['duduk_awal_waktu'],a['rise_start_time'])
    def test_uploaded_session_replay(self):
        p=json.loads(Path('personal_snapshot_regression.json').read_text())
        e=PersonalEngine(Config(**p['config']),PersonalRules(**p['personal_rules']))
        e.set_references(p['personal_calibration']['duduk'],p['personal_calibration']['berdiri'])
        e.rise_threshold=p['calibration']['rise_threshold']
        for row in p['frames']:
            m=row['measurement']
            if m is None:e.missing();continue
            progress=(p['calibration']['seated_y']-m['y'])/(p['calibration']['seated_y']-p['calibration']['standing_y'])
            e.update(row['t'],progress,m['lean'],m['hip'],m['knee'],m['thigh'],m['ankle'])
        self.assertEqual((e.complete,e.cycles),(4,3))
        self.assertEqual(e.results[0]['status_sts'],'MEMENUHI')
        self.assertFalse(e.results[1]['duduk_awal_sesuai'])
        self.assertEqual(e.results[2]['status_sts'],'MEMENUHI')
        self.assertFalse(e.results[3]['duduk_awal_sesuai'])
        for a in e.results:
            if a['duduk_awal_waktu'] is not None:
                self.assertLessEqual(a['duduk_awal_waktu'],a['rise_start_time'])

if __name__=='__main__':unittest.main()
