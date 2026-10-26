"""Local learning API. Run one worker; sessions are stored in memory."""
from contextlib import asynccontextmanager
from mqtt_bridge import MqttBridge
from pathlib import Path
from types import SimpleNamespace
from typing import Literal
from threading import RLock
from functools import wraps
from uuid import uuid4
import json
import os
import math
import statistics
from datetime import datetime, timezone
from fastapi import Query
from database import save_session, list_sessions, load_session
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict
from engine import Config
from personal_engine import PersonalEngine
from personal_rules import PersonalRules, collect_personal, summarize
from calibration import speed_stats
from diagnostics import pose_quality
from measurements import measure
from signals import MAX_SAMPLE_GAP
from serialization import json_scalar

ROOT = Path(__file__).resolve().parent
mqtt_bridge = MqttBridge()

@asynccontextmanager
async def lifespan(app):
    mqtt_bridge.start()
    try:
        yield
    finally:
        mqtt_bridge.stop()

app = FastAPI(title="TA STS — FastAPI", version="0.8.1", lifespan=lifespan)
sessions = {}
DB_PATH = ROOT/'data'/'sts.sqlite3'

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

class NewSession(StrictModel):
    input_source: Literal["browser_camera", "simulation", "unspecified"] = "unspecified"
    width: int = Field(default=640, ge=100, le=4096)
    height: int = Field(default=480, ge=100, le=4096)

class Landmark(StrictModel):
    x: float
    y: float
    z: float = 0
    visibility: float = Field(ge=0, le=1)

class Frame(StrictModel):
    t: float = Field(ge=0, description="Seconds from session origin; strictly increasing")
    landmarks: list[Landmark] | None = Field(default=None, min_length=33, max_length=33)

class Capture(StrictModel):
    posture: str = Field(pattern="^(duduk|berdiri)$")
    delay: float = Field(default=10, ge=0, le=30)

class Session:
    def __init__(self, dimensions):
        self.width, self.height = dimensions.width, dimensions.height
        self.input_source=dimensions.input_source
        self.lock=RLock()
        self.quality={"accepted":False,"reason":"belum_ada_frame"}
        self.frame_interval=None
        self.rules = PersonalRules.load(ROOT/'personal_rules.json')
        self.engine = PersonalEngine(Config(**json.loads((ROOT/'config.json').read_text())),self.rules)
        self.reference_seated = self.reference_standing = None
        self.mode = 'CAL_DUDUK'
        self.last_t = None
        self.filtered = None
        self.pending = None
        self.samples = []
        self.sitting_samples = []
        self.seated = self.standing = None
        self.ready_since = None
        self.rows = []
        self.message = 'Rekam duduk dahulu'
        self.closed = False

    def response(self):
        e = self.engine
        return dict(mode=self.mode, phase=e.state, message=self.message,
                    complete=e.complete, cycles=e.cycles, attempts=e.results,
                    measurement=self.filtered, calibrated=self.standing is not None,
                    calibration_samples=len(self.samples), closed=self.closed,
                    quality=self.quality, frame_interval=self.frame_interval,
                    assessment_mode="personal_dummy_v1", rules=self.rules.model_dump(),
                    personal_calibration={"duduk":self.reference_seated,"berdiri":self.reference_standing},
                    capture=(None if self.pending is None else dict(
                        posture=self.pending["posture"],
                        remaining_seconds=max(0,self.pending["deadline"]-self.last_t) if self.pending["deadline"] is not None and self.last_t is not None else self.pending["delay"],
                        recording=self.pending["deadline"] is not None and self.last_t is not None and self.last_t>=self.pending["deadline"])))

    def ingest(self, frame):
        t = frame.t
        if self.last_t is not None and t <= self.last_t:
            raise HTTPException(409, 'Timestamp harus meningkat; gunakan detik, bukan milidetik')
        if len(self.rows) >= 36000:
            raise HTTPException(409, 'Batas 36000 frame; akhiri sesi lalu buat sesi baru')
        if self.last_t is not None and t-self.last_t > MAX_SAMPLE_GAP:
            self.engine.missing(); self.filtered=None; self.samples=[]; self.ready_since=None
        self.frame_interval=None if self.last_t is None else t-self.last_t
        self.last_t=t
        # Countdown starts on next frame, including missing-pose frames.
        if self.pending and self.pending['deadline'] is None:
            self.pending['deadline']=t+self.pending['delay']
        landmarks = None if frame.landmarks is None else SimpleNamespace(landmark=frame.landmarks)
        result = SimpleNamespace(pose_landmarks=landmarks)
        quality = pose_quality(result)
        try:
            m = measure(result,self.width,self.height) if quality['accepted'] else None
        except ValueError:
            m=None
        if quality["accepted"] and m is None:
            quality["accepted"]=False; quality["reason"]="geometri_tidak_valid"
        self.quality=quality
        if m is None:
            self.filtered=None; self.samples=[]; self.ready_since=None
            self.message=self.engine.missing()
            if self.pending:
                remaining=self.pending['deadline']-t
                self.message=(f'Persiapan {math.ceil(remaining)} detik; menuju posisi {self.pending["posture"]}' if remaining>0 else 'Tubuh belum terbaca; pengambilan posisi menunggu titik kiri terlihat')
        else:
            if self.filtered is None:
                self.filtered=m.copy(); self.filtered['_t']=t-1/30
            alpha=1-math.exp(-max(t-self.filtered['_t'],1e-3)/.12)
            for key in ('y','lean','hip','knee','thigh','ankle'):
                self.filtered[key]+=alpha*(m[key]-self.filtered[key])
            self.filtered['_t']=t
            if self.pending:
                remaining=self.pending['deadline']-t
                self.message=f'Persiapan {max(0,math.ceil(remaining))} detik'
                if remaining<=0:
                    done,reason=collect_personal(self.samples,t,m,self.height,self.rules)
                    self.message=f'Merekam {self.pending["posture"]}: tahan diam {self.rules.calibration_seconds:g} detik. {reason}'
                    if done:
                        self.commit_calibration()
            if self.mode=='KEMBALI':
                progress=(self.seated-self.filtered['y'])/(self.seated-self.standing)
                if progress<=self.engine.cfg.seated_progress and self.engine.seated_geometry(self.filtered['hip']):
                    if self.ready_since is None: self.ready_since=t
                    if t-self.ready_since>=1:
                        self.mode='LATIHAN'
                else:
                    self.ready_since=None
            if self.mode=='LATIHAN':
                f=self.filtered
                progress=(self.seated-f['y'])/(self.seated-self.standing)
                self.message=self.engine.update(t,progress,f['lean'],f['hip'],f['knee'],f['thigh'],f['ankle'],False)
        self.rows.append(dict(t=t,landmarks=None if frame.landmarks is None else [lm.model_dump() for lm in frame.landmarks],measurement=None if self.filtered is None else dict(self.filtered),phase=self.engine.state,mode=self.mode,quality=quality))
        return self.response()

    def commit_calibration(self):
        e=self.engine
        summary=summarize(self.samples)
        if self.pending['posture']=='duduk':
            self.reference_seated=summary
            self.seated=summary['median']['y']
            self.sitting_samples=list(self.samples)
            e.lean_base=summary['median']['lean']
            e.lean_sd=summary['sd']['lean']
            self.mode='CAL_BERDIRI'; self.message='Acuan duduk pribadi tersimpan; rekam berdiri'
        else:
            standing=summary['median']['y']
            seated=self.reference_seated['median']
            if self.seated-standing < self.height*self.rules.calibration_min_rise:
                self.samples=[]; self.message='Kalibrasi berdiri: kenaikan pinggul belum cukup dibanding acuan duduk; ulangi'
                return
            if any(summary['median'][k]-seated[k]<self.rules.calibration_min_extension for k in ('hip','knee')):
                self.samples=[]; self.message='Kalibrasi berdiri: sudut lutut dan badan–paha perlu bertambah dari acuan duduk; ulangi'
                return
            try:
                e.speed_baseline,e.speed_sd,e.rise_threshold=speed_stats(self.sitting_samples,self.seated-standing,e.cfg.speed_sd_multiplier,e.cfg.speed_window)
                e.rise_threshold=max(self.rules.min_rise_speed,e.rise_threshold)
            except ValueError:
                self.pending=None; self.samples=[]; self.mode='CAL_DUDUK'
                self.reference_seated=None; self.seated=None
                self.message='Kalibrasi noise gagal; ulangi dari duduk'
                return
            self.reference_standing=summary
            e.set_references(self.reference_seated,self.reference_standing)
            self.standing=standing; self.mode='KEMBALI'
            self.message='Acuan berdiri pribadi tersimpan; kembali duduk selama 1 detik'
        self.pending=None; self.samples=[]

    def export(self):
        e=self.engine
        return dict(version='0.5.6+api0.8.1',source='TA engine + personal assumed rules',angle_source='geometry_2d',
                    input_source=self.input_source,
                    pose_model=('MediaPipe Tasks Vision 0.10.21 Full float16 v1' if self.input_source=='browser_camera' else None),
                    config=vars(e.cfg),assessment_mode='personal_dummy_v1',
                    assumptions='Angka asumsi teknis IIPP, bukan standar klinis',
                    personal_rules=self.rules.model_dump(),
                    personal_calibration={'duduk':self.reference_seated,'berdiri':self.reference_standing},
                    hand_warning={'enabled':False,'status':'DITUNDA'},
                    dimensions={'width':self.width,'height':self.height},
                    calibration=dict(seated_y=self.seated,standing_y=self.standing,lean_base=e.lean_base,lean_sd=e.lean_sd,speed_baseline=e.speed_baseline,speed_sd=e.speed_sd,rise_threshold=e.rise_threshold),
                    complete=e.complete,cycles=e.cycles,attempts=e.results,frames=self.rows)

def get_session(sid, writable=False):
    if sid not in sessions: raise HTTPException(404,'Sesi tidak ditemukan')
    s=sessions[sid]
    if writable and s.closed: raise HTTPException(409,'Sesi sudah diakhiri')
    return s

def session_locked(fn):
    @wraps(fn)
    def wrapped(sid, *args, **kwargs):
        s=get_session(sid)
        with s.lock:
            return fn(sid,*args,**kwargs)
    return wrapped

@app.get('/runtime-config')
def runtime_config():
    # Public browser configuration only. Never return broker credentials.
    return {'mqtt_ws_url': os.getenv('STS_MQTT_WS_URL', '').strip() or None}

@app.get('/health')
def health(): return {'status':'ok','engine':'TA + personal_dummy_v1','mqtt':mqtt_bridge.status()}

@app.get('/')
def home(): return RedirectResponse('/camera/')

@app.get('/simulation')
def simulation(): return FileResponse(ROOT/'connection_test.html')

@app.get('/sts-client.ts')
def client_source(): return FileResponse(ROOT/'frontend'/'src'/'sts-client.ts',media_type='text/plain')

@app.post('/sessions',status_code=201)
def create_session(body:NewSession):
    if len(sessions)>=10: raise HTTPException(409,'Hapus sesi lama; batas belajar 10 sesi')
    sid=uuid4().hex; sessions[sid]=Session(body)
    result=sessions[sid].response()
    mqtt_bridge.send(sid, sessions[sid].input_source, None, result, force=True)
    return {'session_id':sid,**result}

@app.post('/sessions/{sid}/calibration')
@session_locked
def calibrate(sid:str,body:Capture):
    s=get_session(sid,True)
    expected='CAL_DUDUK' if body.posture=='duduk' else 'CAL_BERDIRI'
    if s.mode!=expected or s.pending:
        raise HTTPException(409,'Urutan: rekam duduk, rekam berdiri, kembali duduk, latihan')
    s.pending=dict(posture=body.posture,delay=body.delay,deadline=None); s.samples=[]
    return s.response()

@app.post('/sessions/{sid}/frames')
@session_locked
def ingest(sid:str,body:Frame):
    s=get_session(sid,True)
    result=s.ingest(body)
    mqtt_bridge.send(sid, s.input_source, s.last_t, result)
    return result

@app.get('/sessions/{sid}')
@session_locked
def status(sid:str): return get_session(sid).response()

@app.post('/sessions/{sid}/finish')
@session_locked
def finish(sid:str):
    s=get_session(sid)
    if not s.closed:
        if s.engine.state=='BANGKIT':
            s.engine.observation_missing=True
            s.engine.finish(s.last_t or 0,False)
        data=json.loads(json.dumps(s.export(),default=json_scalar,allow_nan=False))
        output=ROOT/'results_api'; output.mkdir(exist_ok=True)
        (output/(sid+'.json')).write_text(json.dumps(data,indent=2),encoding='utf-8')
        save_session(DB_PATH, sid, datetime.now(timezone.utc).isoformat(), data)
        s.closed=True
        mqtt_bridge.send(sid, s.input_source, s.last_t, s.response(), force=True)
    return s.response()

@app.get('/sessions/{sid}/export')
@session_locked
def export(sid:str):
    data=get_session(sid).export()
    return json.loads(json.dumps(data,default=json_scalar,allow_nan=False))

@app.delete('/sessions/{sid}',status_code=204)
@session_locked
def delete(sid:str):
    get_session(sid); del sessions[sid]
    mqtt_bridge.forget(sid)

# Compiled React UI, bundled for one-terminal Windows startup.
app.mount('/camera', StaticFiles(directory=ROOT/'frontend'/'dist', html=True, check_dir=False), name='camera')


@app.get('/history')
def history(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return list_sessions(DB_PATH, limit, offset)

@app.get('/history/{sid}')
def history_detail(sid: str):
    record = load_session(DB_PATH, sid)
    if record is None:
        raise HTTPException(404, 'Riwayat sesi tidak ditemukan')
    return record
