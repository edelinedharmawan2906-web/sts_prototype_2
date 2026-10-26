import math
from engine import Engine
from calibration import speed_stats
from itertools import product

for sitting, lean, stand, hand in product((False,True),repeat=4):
    e=Engine();e.start=0;e.initial_sitting=sitting;e.peak=28 if lean else 20;e.hand_hint=hand
    e.finish(2,stand)
    assert e.results[-1]['sts_memenuhi']==(sitting and lean and stand)
for missing in (False,True):
    e=Engine();e.start=0;e.initial_sitting=True;e.peak=28;e.state='BANGKIT'
    if missing:e.missing()
    e.finish(2,True)
    assert (e.results[-1]['sts_memenuhi'] is None)==missing
# Sitting must be captured before leaning, not judged on the leaning frame.
e=Engine();e.rise_threshold=.05
for i in range(15):e.update(i*.1,0,0,90,90,0,0)
for i in range(15,20):e.update(i*.1,0,28,65,90,0,0)
assert e.state=='PERSIAPAN' and e.initial_sitting is True
for i in range(20,30):e.update(i*.1,(i-19)*.08,28,100,130,0,0)
assert e.state=='BANGKIT'
for i in range(30,40):e.update(i*.1,.95,0,175,130,0,0)
assert e.complete==0
for i in range(40,50):e.update(i*.1,.95,0,175,175,0,0)
assert e.complete==1 and e.results[-1]['sts_memenuhi'] is True
for i in range(50,60):e.update(i*.1,0,0,90,90,0,0)
assert e.cycles==1
samples=[(i*.1,{'y':100 + (0.1 if i%2 else -0.1)}) for i in range(15)]
b,sd,threshold=speed_stats(samples,100)
assert sd>0 and abs(threshold-max(1e-6,b+3*sd))<1e-12
try:speed_stats(samples,0)
except ValueError:pass
else:raise AssertionError('Invalid calibration accepted')
print('All tests passed: 16 criterion/hand combinations, missing data, full STS sequence, calibration')

# Real pipeline supplies NumPy scalar comparisons; test disk JSON roundtrip.
import json
import numpy as np
import tempfile
from pathlib import Path
from serialization import json_scalar
for sitting in (np.bool_(False), np.bool_(True)):
    e=Engine(); e.start=0.; e.initial_sitting=sitting; e.peak=np.float64(28); e.hand_hint=np.bool_(True)
    e.finish(np.float64(2), np.bool_(True))
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'session.json'
        path.write_text(json.dumps({'attempts':e.results,'calibration':{'sd':np.float64(.03)}},default=json_scalar))
        saved=json.loads(path.read_text())['attempts'][0]
        assert saved['duduk_awal_sesuai'] is bool(sitting)
        assert saved['indikasi_tangan'] is True
        assert saved['sts_memenuhi'] is bool(sitting)
        assert len(saved['alasan']) == (0 if sitting else 1)
# Exercise production update with NumPy posture values.
e=Engine()
for i in range(15): e.update(i*.05,0,0,90,90,0,np.float64(0))
assert type(e.last_sitting) is bool
print('NumPy values saved to JSON with correct boolean types and reasons')
# No attempt can start without a multi-frame seated observation.
e=Engine();e.rise_threshold=.05
for i in range(20):e.update(i*.03,0,28,70,90,0,0)
assert e.state=='DUDUK' and not e.results
# A single posture spike should not flip seated median.
e=Engine();e.rise_threshold=.05
for i in range(30):e.update(i*.03,0,0,90,90,0,0)
e.update(.90,0,0,115,90,0,0)
assert e.last_sitting is True
# Noisy plateau vs continuous rise; no acceptance of continued rise.
from signals import WindowSpeed
f=WindowSpeed(.2)
for i in range(50):
    v=f.update(i*.03,.5*i*.03)
assert abs(v-.5)<1e-8
f.clear()
assert f.update(2,1) is None
print('Readiness, sitting median and causal velocity tests passed')

from calibration import collect_calibration
samples=[]
for i in range(20):assert not collect_calibration(samples,i*.03,{'y':100})
assert not collect_calibration(samples,.6,None) and not samples
# No second D/B needed: fresh uninterrupted run completes.
for i in range(35):done=collect_calibration(samples,1+i*.03,{'y':100})
assert done
assert samples[0][0]==1
# Silent timestamp gap cannot count as continuous recording.
assert not collect_calibration(samples,4,{'y':100}) and len(samples)==1
print('Calibration interruption, automatic resampling and gap tests passed')

from types import SimpleNamespace
from diagnostics import pose_quality
lm=[SimpleNamespace(visibility=1.) for _ in range(33)]
r=SimpleNamespace(pose_landmarks=SimpleNamespace(landmark=lm))
assert pose_quality(r)['accepted']
lm[27].visibility=.64
assert not pose_quality(r)['accepted'] and 'pergelangan_kaki' in pose_quality(r)['reason']
lm[27].visibility=.65
assert pose_quality(r)['accepted']
assert not pose_quality(SimpleNamespace(pose_landmarks=None))['accepted']
print('Visibility diagnostics tests passed')

# Slow/jittered processing must still provide a derivative and full STS sequence.
for dt in (.033, .1, .12, .2):
    f=WindowSpeed(.2)
    for i in range(30):
        v=f.update(i*dt,.4*i*dt)
        if i>=2 and i*dt>=.2: assert v is not None and abs(v-.4)<1e-8
    assert f.update(30*dt+.5,1) is None
    samples=[]
    for i in range(60):
        if collect_calibration(samples,i*dt,{'y':100}):break
    assert len(samples)>=9
    assert speed_stats(samples,100)==(0.,0.,1e-6)
    e=Engine();e.rise_threshold=.05
    t=0.
    def feed(seconds,p,lean,hip,knee):
        global t
        for _ in range(round(seconds/dt)):
            e.update(t,p(t) if callable(p) else p,lean,hip,knee,0,0)
            t+=dt
    feed(2,0,0,90,90)
    assert e.last_sitting is True
    feed(1,0,28,65,90)
    begin=t
    feed(2,lambda now:min(.95,(now-begin)*.5),28,100,130)
    assert e.state=='BANGKIT'
    feed(1,.95,0,175,130)
    assert e.complete==0  # Bent knee still blocks standing.
    feed(2,.95,0,175,175)
    assert e.complete==1
    feed(1,0,0,90,90)
    assert e.cycles==1
    e.update(t,0,0,90,90,0,0)
    assert not e.standing_checks  # No stale checks in a new seated stage.
# A long gap cancels a partly accumulated hold and marks interrupted attempt.
e=Engine();e.state='BANGKIT';e.start=0;e.initial_sitting=True;e.peak=28
for t in (0,.1,.2):e.update(t,.95,0,175,175,0,0)
e.update(1,.95,0,175,175,0,0)
assert e.complete==0 and e.observation_missing and e.velocity is None
print('v0.5: slow sampling, unchanged posture checks, calibration, gaps and stale diagnostics passed')

# Counting works without a seated quality baseline, and a long standing plateau
# is counted once. Missing pose invalidates quality, never bridges a hold.
def recover_sequence(interrupted=False, low_lean=False):
    e=Engine();e.rise_threshold=.05
    for i in range(15):e.update(i*.1,0,0,90,90,0,0)
    if interrupted:e.missing()
    lean=0 if low_lean else 28
    for i in range(15,20):e.update(i*.1,0,lean,90-lean,90,0,0)
    for i in range(20,35):e.update(i*.1,min(.95,(i-19)*.08),lean,100,130,0,0)
    for i in range(35,65):e.update(i*.1,.95,0,175,175,0,0)
    assert e.complete==1
    for i in range(65,75):e.update(i*.1,0,0,90,90,0,0)
    assert e.cycles==1
    return e
r=recover_sequence(True).results[0]
assert r['bangkit_lengkap'] and r['duduk_awal_sesuai'] is None
assert r['status_sts']=='BELUM DAPAT DINILAI' and r['duduk_awal_pengukuran']=={}
r=recover_sequence(False,True).results[0]
assert r['bangkit_lengkap'] and not r['minimum_terpenuhi']
assert r['status_sts']=='BELUM MEMENUHI'
# Standing on startup is not an observed sit-to-stand.
e=Engine();e.rise_threshold=.05
for i in range(50):e.update(i*.1,.95,0,175,175,0,0)
assert e.complete==0
# An expired seated anchor cannot authorize an unseen rise after a long gap.
e=Engine();e.rise_threshold=.05
for i in range(15):e.update(i*.1,0,0,90,90,0,0)
e.missing()
for i in range(50,70):e.update(i*.1,.95,28,175,175,0,0)
assert e.complete==0
# Replay original accepted angle rows and rejected-frame events. Old files lack
# thigh, ankle, hand and calibrated lean baseline/SD: test counts ONLY. NaN
# posture fields intentionally prevent asserting a valid quality result.
fixture=json.loads((Path(__file__).parent/'count_regression.json').read_text())
for lean_base in (0.,2.,3.):
    e=Engine();e.rise_threshold=fixture['rise_threshold'];e.lean_base=lean_base
    for row in fixture['events']:
        if row is None:e.missing()
        else:e.update(*row,float('nan'),float('nan'))
    assert (e.complete,e.cycles)==(4,3),(lean_base,e.complete,e.cycles)
    assert e.rise_attempts==4 and len(e.results)==4
print('v0.5.1: independent counts/quality, recovery, no double count, stale origin and session regression (4/3) passed')

# Preparation alone is not an STS attempt, including repeated bends.
e=Engine();e.rise_threshold=.05
for i in range(15):e.update(i*.1,0,0,90,90,0,0)
for i in range(15,25):e.update(i*.1,0,12,78,90,0,0)
assert e.state=='PERSIAPAN' and not e.results and e.rise_attempts==0
for i in range(25,40):e.update(i*.1,0,0,90,90,0,0)
assert e.state=='DUDUK' and not e.results and e.rise_attempts==0
# A confirmed rise with an unobserved standing plateau is unknown, never false
# and never a fabricated complete/cycle count.
e=Engine();e.rise_threshold=.05
for i in range(15):e.update(i*.1,0,0,90,90,0,0)
for i in range(15,20):e.update(i*.1,0,28,65,90,0,0)
for i in range(20,30):e.update(i*.1,(i-19)*.08,28,100,130,0,0)
assert e.state=='BANGKIT' and e.rise_attempts==1
e.missing()
for i in range(50,65):e.update(i*.1,0,0,90,90,0,0)
assert e.complete==0 and e.cycles==0 and e.returned_attempts==1
assert len(e.results)==1 and e.results[0]['bangkit_lengkap'] is None
assert e.results[0]['status_berdiri']=='BELUM DAPAT DIKONFIRMASI'
assert e.results[0]['sts_memenuhi'] is None and 'Berdiri ?' in e.assessment_text()
# Exact feature replay of the newer session: no rerun of MediaPipe, no model
# guesses during rejected frames, and no relaxation of the 0.65 quality gate.
from engine import Config
fixture=json.loads((Path(__file__).parent/'interrupted_regression.json').read_text())
e=Engine(Config(**fixture['config']))
for key in ('lean_base','lean_sd','rise_threshold'):setattr(e,key,fixture['calibration'][key])
for row in fixture['events']:
    if row is None:e.missing()
    else:e.update(*row)
assert (e.complete,e.cycles,e.rise_attempts,e.returned_attempts)==(3,2,4,3)
assert len(e.results)==4
assert [r['bangkit_lengkap'] for r in e.results]==[True,True,None,True]
assert e.results[2]['status_sts']=='BELUM DAPAT DINILAI'
# New baseline collection during preparation can recover an actual snapshot;
# interruption still keeps quality unknown. Counts/standing evidence unchanged.
assert e.results[1]['duduk_awal_sesuai'] is None
assert all(r['status_sts']=='BELUM DAPAT DINILAI' for r in e.results[1:])
print('v0.5.2: no preparation-only attempts; unknown standing preserved; newer session 4 attempts / 3 confirmed / 1 unknown passed')

# v0.5.3: preserve snapshot and partial window across cancelled preparation,
# without refreshing its timestamp or authorizing a count from leaning alone.
for initial_ok in (False, True):
    e=Engine();e.rise_threshold=.05
    for i in range(15): e.update(i*.05,0,0,90 if initial_ok else 105,90,0,0)
    original=e.last_sitting_t
    for i in range(15,23): e.update(i*.05,0,12,78,90,0,0)
    assert e.state=='PERSIAPAN'
    for i in range(23,31): e.update(i*.05,0,0,90,90,0,0)
    assert e.state=='DUDUK' and e.last_sitting is initial_ok
    assert e.last_sitting_t==original
    assert e.complete==e.cycles==e.rise_attempts==0 and not e.results
    # A new valid median can form using stable samples across cancellation.
    for i in range(31,35):e.update(i*.05,0,0,90,90,0,0)
    assert e.last_sitting is True and e.last_sitting_t>original
    # Actual subsequent rise is one attempt, despite the earlier lean.
    for i in range(35,45):e.update(i*.05,0,28,65,90,0,0)
    for i in range(45,75):e.update(i*.05,min(.95,(i-44)*.04),28,100,130,0,0)
    for i in range(75,100):e.update(i*.05,.95,0,175,175,0,0)
    assert e.complete==1 and e.rise_attempts==1
    assert e.results[0]['duduk_awal_sesuai'] is True
# Expired evidence and evidence interrupted during preparation cannot return.
for gap in (False,True):
    e=Engine();e.state='PERSIAPAN';e.initial_sitting=True
    e.initial_sitting_t=0;e.initial_sitting_details={'hip':90}
    if gap:e.missing()
    e.discard_preparation(.5 if gap else 3.)
    assert e.last_sitting is None and e.last_sitting_t is None
# Small shifts below existing rise progress gate never add attempts.
e=Engine();e.rise_threshold=.05
for i in range(30):e.update(i*.05,0,0,90,90,0,0)
for i in range(30,230):
    e.update(i*.05,.025*(1+math.sin(i*.15)),12 if i%40<20 else 0,90,90,0,0)
assert e.complete==e.cycles==e.rise_attempts==0 and not e.results

fixture=json.loads((Path(__file__).parent/'full_regression.json').read_text())
e=Engine(Config(**fixture['config']))
for key in ('lean_base','lean_sd','rise_threshold'):setattr(e,key,fixture['calibration'][key])
for row in fixture['events']:
    if row is None:e.missing()
    else:e.update(*row)
assert (e.complete,e.cycles,e.rise_attempts)==(4,3,4)
# v056 bounded seated windows now recover evidence for the last two rises.
assert [r['status_sts'] for r in e.results]==['BELUM MEMENUHI']*4
assert all(r['duduk_awal_sesuai'] is False for r in e.results)
assert [r['duduk_awal_waktu'] for r in e.results[:2]]==[38.25,45.64099999999962]
print('v0.5.3: snapshot age/gaps, cancellation window, no lean/shift counts, Full replay 4/3 passed')

from hand_warning import hand_measure,HandWarning
import math
lm=[SimpleNamespace(x=0.,y=0.,visibility=1.) for _ in range(33)]
lm[11].x=.2;lm[11].y=.2
lm[23].x=.2;lm[23].y=.6
lm[25].x=.6;lm[25].y=.6
for i in (15,17,19,21):lm[i].x=.4;lm[i].y=.3
r=SimpleNamespace(pose_landmarks=SimpleNamespace(landmark=lm))
assert hand_measure(r,1000,1000)['hand_raw'] is False
# Wrist far, finger near thigh: new detector recognizes the finger.
lm[19].y=.59
m=hand_measure(r,1000,1000)
assert m['hand_raw'] is True and m['hand_point']=='index'
assert m['hand_distance_wrist']>.12 and m['hand_distance_index']<.12
# Pixel metric, independent of aspect ratio and low ankle visibility.
lm[27].visibility=0
assert hand_measure(r,1600,900)['hand_raw'] is True
lm[19].visibility=.64
assert hand_measure(r,1000,1000)['hand_raw'] is False
for i in (15,17,19,21):lm[i].visibility=0
assert hand_measure(r,1000,1000)['hand_raw'] is None
lm[25].visibility=.64
assert hand_measure(r,1000,1000)['hand_reason']=='shoulder_hip_knee_unreliable'
assert hand_measure(SimpleNamespace(pose_landmarks=None),1000,1000)['hand_raw'] is None
# Debounce: a spike never warns, sustained proximity does, short exit
# doesn't flicker; unknown/gaps immediately remove warning and restart timing.
h=HandWarning()
assert h.update(0,True) is None
assert h.update(.1,False) is None
assert h.update(.3,False) is False
assert h.update(.4,True) is False
assert h.update(.55,True) is True
assert h.update(.6,False) is True
assert h.update(.7,True) is True
assert h.update(.8,None) is None
assert h.update(.9,True) is None
assert h.update(1.05,True) is True
assert h.update(2,True) is None
assert h.update(2.15,True) is True
assert h.update(2.2,False) is True
assert h.update(2.4,False) is False
print('v0.5.3: hand points, unreliable landmarks, debounce and gaps passed')

# v0.5.4 plateau fallback preserves geometry/hold and adds no gap bridging.
from standing import StandingStability
from hand_warning import warning_context
for dt in (.03,.1,.12,.2):
    f=StandingStability(.5)
    for i in range(60):
        t=i*dt
        good=f.update(t,1+.035*t+.003*math.sin(20*t),True,.08)
    assert good,(dt,f.speed,f.excursion,f.span)
    assert not f.update(t+1,1,True,.08)  # large gap clears all evidence
    assert f.speed is None
    assert not f.update(t+1.1,1,False,.08) and not f.samples
# Sustained rising and large oscillations cannot qualify as a plateau.
for motion in (lambda t:1+.12*t, lambda t:1+.08*math.sin(18*t)):
    f=StandingStability(.5)
    for i in range(100):
        t=i*.03;ok=f.update(t,motion(t),True,.08)
        if i>20:assert not ok
for motion in (lambda t:1+.12*t,lambda t:1+.08*math.sin(18*t)):
    e=Engine();e.state='BANGKIT';e.start=0;e.initial_sitting=True;e.peak=28
    for i in range(100):
        t=i*.03;e.update(t,motion(t),0,175,175,0,0)
    assert e.complete==0
# Bent knee never passes even on a flat, stable plateau.
e=Engine();e.state='BANGKIT';e.start=0;e.initial_sitting=True;e.peak=28
for i in range(100):e.update(i*.03,1,0,175,160,0,0)
assert e.complete==0 and not e.standing_filter.samples
# Even with complete plateau history, missing input cancels the confirmation
# timer. New reliable frames must form a new uninterrupted hold.
e=Engine();e.state='BANGKIT';e.start=0;e.initial_sitting=True;e.peak=28
for i in range(11):e.update(i*.03,1,0,175,175,0,0)
assert e.complete==0
e.missing()
assert not e.standing_filter.samples and not e.since
for i in range(12,19):e.update(i*.03,1,0,175,175,0,0)
assert e.complete==0
for i in range(19,70):e.update(i*.03,1,0,175,175,0,0)
assert e.complete==1 and e.results[0]['sts_memenuhi'] is None
# Display and assessment use the same phase predicate, including BANGKIT while
# waiting at an upright plateau. Ordinary standing proximity is excluded.
for state in ('DUDUK','BERDIRI'):
    assert not warning_context(state,.3,100,130)
for state in ('PERSIAPAN','BANGKIT'):
    assert warning_context(state,.3,100,130)
    assert not warning_context(state,1,175,175)
assert not warning_context('BANGKIT',float('nan'),175,175)
e=Engine();e.state='BANGKIT';e.start=0;e.initial_sitting=True;e.peak=28
for i in range(40):e.update(i*.03,1,0,175,175,0,0,True)
assert e.complete==1 and not e.results[0]['indikasi_tangan']
# Latest session replay also replays the new phase-gated hand debounce from RAW
# saved proximity, rather than claiming that old per-attempt flags still apply.
fixture=json.loads((Path(__file__).parent/'latest_regression.json').read_text())
e=Engine(Config(**fixture['config']));h=HandWarning()
for key in ('lean_base','lean_sd','rise_threshold'):setattr(e,key,fixture['calibration'][key])
for event in fixture['events']:
    if event is None:e.missing();h.reset();continue
    row=event['measurement'];t,p,lean,hip,knee,thigh,ankle=row
    ctx=warning_context(e.state,p,hip,knee,e.cfg.stand_progress,e.cfg.straight_tolerance)
    active=h.update(t,event['hand_raw'] if ctx else None)
    e.update(*row,active is True)
    if not warning_context(e.state,p,hip,knee,e.cfg.stand_progress,e.cfg.straight_tolerance):h.reset()
assert (e.complete,e.cycles,e.rise_attempts,e.returned_attempts)==(3,2,3,2)
assert all(r['bangkit_lengkap'] is True for r in e.results)
assert all(r['status_sts']=='BELUM MEMENUHI' for r in e.results)
assert all(not r['indikasi_tangan'] for r in e.results)
assert all(r['duduk_awal_sesuai'] is False for r in e.results)
print('v0.5.4: bounded plateau, rising/oscillation rejection, knee, missing hold, phase-gated hands, latest session 3/2 passed')
from test_app_smoke import run as app_smoke
app_smoke()

# v055: latest full session and reports retain all failed/unknown criteria.
fixture=json.loads((Path(__file__).parent/'session002619_regression.json').read_text())
e=Engine(Config(**fixture['config']))
for key in ('lean_base','lean_sd','rise_threshold'):setattr(e,key,fixture['calibration'][key])
for event in fixture['events']:
    if event is None:e.missing()
    else:e.update(*event)
assert (e.complete,e.cycles,e.rise_attempts)==(4,3,4)
assert len(e.results)==4
for result in e.results:
    assert result['status_sts']=='BELUM MEMENUHI'
    report=result['penilaian_tahap']
    assert report['duduk']['memenuhi'] is False
    assert report['duduk']['pengukuran']['thigh']['memenuhi'] is False
    assert report['condong']['memenuhi'] is True and report['berdiri']['memenuhi'] is True
    assert report['bantuan_tangan']['dinilai'] is False
from assessment import stage_report,display_lines
r=stage_report({},None,28,None,True,{},Config())
assert r['condong']['memenuhi'] is None
assert all(x['memenuhi'] is None for x in r['duduk']['pengukuran'].values())
r=stage_report(dict(hip=100,lean=10,thigh=10,ankle=.15),True,25,True,False,{},Config())
assert all(x['memenuhi'] for x in r['duduk']['pengukuran'].values())
assert r['condong']['memenuhi'] is True
print('v0.5.5: 002619 regression 4/3, four failed sitting assessments, stage detail and threshold boundaries passed')

# v056: reject low seated excursions with or without preparation.
for lean in (0,28):
    e=Engine();e.rise_threshold=.01
    for i in range(50):e.update(i*.05,0,0,90,90,0,0)
    for i in range(50,65):e.update(i*.05,0,lean,90,90,0,0)
    for i in range(65,85):e.update(i*.05,min(.12,(i-65)*.01),lean,95,95,0,0)
    for i in range(85,110):e.update(i*.05,.12,lean,95,95,0,0)
    for i in range(110,150):e.update(i*.05,0,0,90,90,0,0)
    assert e.rise_attempts==0 and not e.results
# A genuine incomplete rise beyond the seated band must still be reported.
e=Engine();e.rise_threshold=.01
for i in range(50):e.update(i*.05,0,0,90,90,0,0)
for i in range(50,70):e.update(i*.05,min(.35,(i-50)*.03),0,115,120,0,0)
for i in range(70,90):e.update(i*.05,.35,0,115,120,0,0)
for i in range(90,120):e.update(i*.05,0,0,90,90,0,0)
assert e.rise_attempts==1 and e.results[0]['bangkit_lengkap'] is False
# Boundary p=.20 is still in the seated band and cannot confirm a rise.
e=Engine();e.rise_threshold=.01
for i in range(40):e.update(i*.05,0,0,90,90,0,0)
for i in range(40,60):e.update(i*.05,min(.20,(i-40)*.02),0,110,110,0,0)
assert e.rise_attempts==0
from sitting import SittingEvidence
f=SittingEvidence(.5)
for i in range(20):r=f.update(i*.05,.1+.003*math.sin(i*2),115,5,15,.03,True,.08)
assert r is not None and r['hip']==115 and r['thigh']==15
# Passing stability does not turn out-of-range postures into correct postures.
assert not (abs(r['hip']-90)<=10 and r['thigh']<=10)
for motion in (lambda t:.12*t,lambda t:.04*math.sin(25*t)):
    f=SittingEvidence(.5)
    for i in range(40):
        r=f.update(i*.03,motion(i*.03),90,0,0,0,True,.08)
        if i>20:assert r is None
f=SittingEvidence(.5)
for i in range(10):r=f.update(i*.05,.1,90,0,0,0,True,.08)
assert r is not None
assert f.update(.50,.1,90,0,0,0,False,.08) is None
assert not f.samples
assert f.update(1.5,.1,90,0,0,0,True,.08) is None
fixture=json.loads((Path(__file__).parent/'morning_regression.json').read_text())
e=Engine(Config(**fixture['config']))
for key in ('lean_base','lean_sd','rise_threshold'):setattr(e,key,fixture['calibration'][key])
for event in fixture['events']:
    if event is None:e.missing()
    else:e.update(*event)
assert (e.rise_attempts,e.complete,e.cycles,e.returned_attempts)==(4,4,3,3)
assert len(e.results)==4 and all(r['status_sts']=='BELUM MEMENUHI' for r in e.results)
assert all(r['penilaian_tahap']['duduk']['memenuhi'] is False for r in e.results)
assert e.results[-1]['duduk_awal_metode']=='bounded_window'
assert all(r['kemiringan_puncak']>=25 and r['bangkit_lengkap'] for r in e.results)
assert not any(58.5<r['start_time']<60 or 67<r['start_time']<68.5 for r in e.results)
print('v0.5.6: low shifts rejected; incomplete rises preserved; seated windows bounded; morning replay 4/4/3 with four seated assessments')

e=Engine();e.rise_threshold=.01
for i in range(30):e.update(i*.05,0,0,90,90,0,0)
assert e.sitting_evidence.samples
e.missing()
assert not e.sitting_evidence.samples and e.last_sitting is None
for i in range(30,35):e.update(i*.05,0,0,90,90,0,0)
assert e.last_sitting is None
