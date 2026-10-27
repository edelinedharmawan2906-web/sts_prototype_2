"""Session-specific assumed assessment built on the existing TA state machine."""
from engine import Engine
from collections import deque
from sitting import SittingEvidence
from signals import MAX_SAMPLE_GAP

class PersonalEngine(Engine):
    reference_label='Asumsi teknis IIPP personal_dummy_v1; bukan standar klinis'
    def __init__(self,cfg,rules):
        super().__init__(cfg)
        self.rules=rules
        self.references={}
        self.seated_snapshots=deque()
        self.capture_window=SittingEvidence(self.cfg.sitting_window)
        self.rise_start_time=None
        for key in ('stand_progress','seated_progress','stable_speed','hold_seconds'):
            setattr(self.cfg,key,getattr(rules,key))

    def set_references(self,seated,standing):
        self.references={'duduk':seated,'berdiri':standing}
        self.lean_base=seated['median']['lean']
        self.lean_sd=seated['sd']['lean']
        self.cfg.lean_min=self.lean_base+self.rules.lean_addition

    def seated_geometry(self,hip):
        ref=self.references.get('duduk')
        return ref is not None and abs(hip-ref['median']['hip'])<=self.rules.seated_anchor_tolerance

    def sitting_matches(self,hip,lean,thigh,ankle):
        ref=self.references.get('duduk')
        if not ref:return False
        return all(abs(v-ref['median'][k])<=tol+1e-9 for k,v,tol in (
            ('hip',hip,self.rules.sitting_angle_tolerance),('lean',lean,self.rules.sitting_angle_tolerance),
            ('thigh',thigh,self.rules.sitting_angle_tolerance),('ankle',ankle,self.rules.sitting_ankle_tolerance)))

    def sitting_sample_gate(self,lean,progress):
        # The personal mode has its own posture-independent stable-window collector.
        return False

    def collect_seated(self,t,p,lean,hip,thigh,ankle):
        eligible=self.state in ('DUDUK','PERSIAPAN') and p<=self.cfg.seated_progress
        m=self.capture_window.update(t,p,hip,lean,thigh,ankle,eligible,self.cfg.stable_speed)
        if m is None:return
        rows=self.capture_window.samples
        for index in (2,3,4):
            values=[r[index] for r in rows]
            if max(values)-min(values)>self.rules.sitting_capture_angle_range:return
        values=[r[5] for r in rows]
        if max(values)-min(values)>self.rules.sitting_capture_ankle_range:return
        passed=self.sitting_matches(m['hip'],m['lean'],m['thigh'],m['ankle'])
        self.last_sitting_t=t;self.last_sitting=passed
        self.sitting_details=dict(m);self.sitting_source='personal_stable_window'
        self.sitting_history={'time':t,'measurement':dict(m)}
        self.seated_snapshots.append(dict(time=t,passed=passed,measurement=dict(m),source=self.sitting_source))

    def missing(self):
        self.seated_snapshots.clear();self.capture_window.clear()
        return super().missing()

    def select_seated(self,t):
        candidates=[r for r in self.seated_snapshots
                    if 0<=t-r['time']<=self.cfg.seated_evidence_max_age]
        r=candidates[-1] if candidates else None
        self.last_sitting_t=None if r is None else r['time']
        self.last_sitting=None if r is None else r['passed']
        self.sitting_details={} if r is None else dict(r['measurement'])
        self.sitting_source=None if r is None else r['source']
        self.sitting_history=None if r is None else {'time':r['time'],'measurement':dict(r['measurement'])}

    def begin_attempt(self,t,lean,hand,state):
        self.rise_start_time=t if state=='BANGKIT' else None
        self.select_seated(t)
        return super().begin_attempt(t,lean,hand,state)

    def on_rise_started(self,t):
        # Freeze evidence BEFORE hip rise, which can follow a seated preparation.
        self.rise_start_time=t
        if self.initial_sitting is not None and self.initial_sitting_t is not None and self.initial_sitting_t<=t:
            return
        self.select_seated(t)
        self.initial_sitting=self.last_sitting
        self.initial_sitting_t=self.last_sitting_t
        self.initial_sitting_details=dict(self.sitting_details)
        self.initial_sitting_source=self.sitting_source

    def finish(self,t,success):
        result=super().finish(t,success)
        self.results[-1]['rise_start_time']=self.rise_start_time
        self.results[-1]['sitting_capture_version']='stable_window_v2'
        self.seated_snapshots.clear();self.capture_window.clear()
        return result

    def preparation_threshold(self):
        return self.lean_base+self.rules.preparation_lean_delta

    def standing_targets(self):
        ref=self.references['berdiri']['median']
        return max(0,ref['hip']-self.rules.standing_angle_tolerance),max(0,ref['knee']-self.rules.standing_angle_tolerance)

    def update(self,t,p,lean,hip,knee,thigh,ankle,hand=False):
        if self.last_t is not None and (t<=self.last_t or t-self.last_t>MAX_SAMPLE_GAP):self.missing()
        self.collect_seated(t,p,lean,hip,thigh,ankle)
        if self.state=='BANGKIT':self.peak=max(self.peak,lean)
        saved=None
        if self.state=='PERSIAPAN' and self.initial_sitting is not None:
            saved=(self.initial_sitting,self.initial_sitting_t,dict(self.initial_sitting_details),self.initial_sitting_source)
        text=super().update(t,p,lean,hip,knee,thigh,ankle,hand)
        # Once observed, preserve the initial posture through preparation.
        # A later, deliberately leaned posture must not replace it.
        if saved is not None and self.state in ('PERSIAPAN','BANGKIT'):
            if self.state!='BANGKIT' or (saved[1] is not None and self.rise_start_time is not None and saved[1]<=self.rise_start_time):
                self.initial_sitting,self.initial_sitting_t,self.initial_sitting_details,self.initial_sitting_source=saved
                self.sitting_history={'time':saved[1],'measurement':dict(saved[2])}
        keep=self.cfg.seated_evidence_max_age+self.cfg.hold_seconds
        while self.seated_snapshots and t-self.seated_snapshots[0]['time']>keep:
            self.seated_snapshots.popleft()
        return {'Posisi awal sesuai; mulai condong':'Posisi awal dekat acuan pribadi; mulai gerakan',
                'Sesuaikan posisi duduk: badan tegak, paha mendatar, kaki di bawah lutut':'Posisi duduk berbeda dari acuan pribadi; lihat rincian setelah bangkit',
                'Bangkit lengkap terdeteksi':'Acuan berdiri pribadi tercapai',
                'Kemiringan minimum terpenuhi':'Tambahan kemiringan dari acuan pribadi terpenuhi'}.get(text,text)

    def make_report(self,success):
        sit={}
        for key in ('hip','lean','thigh','ankle'):
            baseline=self.references['duduk']['median'][key]
            tol=self.rules.sitting_ankle_tolerance if key=='ankle' else self.rules.sitting_angle_tolerance
            value=self.initial_sitting_details.get(key)
            unit='panjang torso' if key=='ankle' else 'derajat'
            sit[key]=dict(nilai=value,acuan=baseline,toleransi=tol,
                selisih=None if value is None else value-baseline,
                target=f'{baseline:.3f} +/- {tol:g} {unit}',
                memenuhi=None if value is None else bool(abs(value-baseline)<=tol+1e-9))
        hip_target,knee_target=self.standing_targets()
        end=dict(self.standing_measurements)
        ref=self.references['berdiri']['median']
        return dict(rule_set='personal_dummy_v1',acuan=self.reference_label,
            duduk=dict(memenuhi=self.initial_sitting,pengukuran=sit,ringkasan='Dibanding median kalibrasi duduk pribadi'),
            condong=dict(memenuhi=None if self.observation_missing else bool(self.peak>=self.cfg.lean_min),
                puncak_teramati=self.peak,minimum=self.cfg.lean_min,acuan=self.lean_base,
                tambahan_teramati=self.peak-self.lean_base,minimum_tambahan=self.rules.lean_addition),
            berdiri=dict(memenuhi=success,pengukuran_saat_keputusan=end,
                acuan_hip=ref['hip'],acuan_knee=ref['knee'],target_hip=hip_target,target_knee=knee_target,
                selisih_hip=None if end.get('hip') is None else end['hip']-ref['hip'],
                selisih_knee=None if end.get('knee') is None else end['knee']-ref['knee'],
                target_progress=self.cfg.stand_progress,hold_seconds=self.cfg.hold_seconds,stable_speed=self.cfg.stable_speed),
            bantuan_tangan=dict(dinilai=False,status='DITUNDA'))
