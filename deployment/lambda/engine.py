from dataclasses import dataclass
from collections import deque
from statistics import median
from signals import WindowSpeed, MAX_SAMPLE_GAP
from standing import StandingStability
from sitting import SittingEvidence
from hand_warning import warning_context

@dataclass
class Config:
    lean_min: float = 25.0
    sitting_tolerance: float = 10.0
    straight_tolerance: float = 15.0
    stand_progress: float = .9
    seated_progress: float = .2
    stable_speed: float = .08
    hold_seconds: float = .3
    speed_sd_multiplier: float = 3.0
    speed_window: float = .2
    sitting_window: float = .5
    seated_evidence_max_age: float = 2.0
    standing_window: float = .5

class Engine:
    def __init__(self, cfg=None):
        self.cfg = cfg or Config()
        self.velocity_filter = WindowSpeed(self.cfg.speed_window)
        self.standing_filter = StandingStability(self.cfg.standing_window)
        self.velocity = None
        self.sitting_samples = deque()
        self.sitting_evidence = SittingEvidence(self.cfg.sitting_window)
        self.sitting_details = {}
        self.standing_checks = {}
        self.standing_measurements = {}
        self.stability_details = {}
        self.best_standing_hold = 0.
        self.standing_blockers = {}
        self.state = 'DUDUK'
        self.start = None
        self.peak = 0.
        self.complete = 0
        self.cycles = 0
        self.rise_attempts = 0
        self.returned_attempts = 0
        self.results = []
        self.initial_sitting_source = None
        self.sitting_source = None
        self.initial_sitting_t = None
        self.initial_sitting_details = {}
        self.initial_sitting = None
        self.last_sitting = None
        self.last_sitting_t = None
        self.seated_anchor_t = None
        self.sitting_history = None
        self.observation_missing = False
        self.speed_baseline = None
        self.speed_sd = None
        self.rise_threshold = None
        self.last_t = None
        self.last_p = None
        self.since = {}
        self.hand_hint = False
        self.lean_base = 0.
        self.lean_sd = 1.

    def sitting_matches(self, hip, lean, thigh, ankle):
        c=self.cfg
        return bool(abs(hip-90)<=c.sitting_tolerance and lean<=c.sitting_tolerance and thigh<=c.sitting_tolerance and ankle<=.15)

    def seated_geometry(self, hip):
        return hip < 120

    def sitting_sample_gate(self, lean, progress):
        return lean <= self.lean_base+max(3*self.lean_sd,3) and progress<=self.cfg.seated_progress

    def preparation_threshold(self):
        return self.lean_base+max(3*self.lean_sd,3)

    def standing_targets(self):
        return 180-self.cfg.straight_tolerance, 180-self.cfg.straight_tolerance

    def make_report(self, success):
        from assessment import stage_report
        return stage_report(self.initial_sitting_details,self.initial_sitting,self.peak,success,self.observation_missing,self.standing_measurements,self.cfg)

    def on_rise_started(self, t):
        pass

    def held(self, key, condition, t):
        if not condition:
            self.since.pop(key, None)
            return False
        self.since.setdefault(key, t)
        return t-self.since[key] >= self.cfg.hold_seconds

    def missing(self):
        if self.state in ("PERSIAPAN", "BANGKIT"):
            self.observation_missing = True
        self.last_sitting = None
        self.last_sitting_t = None
        self.sitting_details = {}
        self.sitting_samples.clear()
        self.sitting_evidence.clear()
        self.velocity_filter.clear()
        self.velocity = None
        self.standing_checks = {}
        self.stability_details = {}
        self.since.clear()
        self.standing_filter.clear()
        self.last_t = self.last_p = None
        return 'Posisi tubuh belum terbaca; penilaian ditunda'

    def begin_attempt(self, t, lean, hand, state):
        self.standing_filter.clear()
        fresh = self.last_sitting_t is not None and 0 <= t-self.last_sitting_t <= self.cfg.seated_evidence_max_age
        self.initial_sitting_source = self.sitting_source if fresh else None
        self.initial_sitting = self.last_sitting if fresh else None
        self.initial_sitting_t = self.last_sitting_t if fresh else None
        self.initial_sitting_details = dict(self.sitting_details) if fresh else {}
        if not fresh: self.sitting_details = {}
        self.observation_missing = False
        self.start = t
        self.best_standing_hold = 0.
        self.standing_blockers = {}
        self.peak = lean
        self.hand_hint = hand
        self.state = state
        if state == 'BANGKIT': self.rise_attempts += 1
        self.seated_anchor_t = None
        self.since.clear()

    def update(self, t, p, lean, hip, knee, thigh, ankle, hand=False):
        c = self.cfg
        self.standing_measurements = dict(progress=float(p), hip=float(hip), knee=float(knee))
        if self.last_t is not None and (t<=self.last_t or t-self.last_t>MAX_SAMPLE_GAP):
            self.missing()
        self.standing_checks = {}
        self.stability_details = {}
        v = self.velocity_filter.update(t,p)
        self.velocity = v
        self.last_t, self.last_p = t, p
        if self.state in ('DUDUK', 'PERSIAPAN'):
            seated_pose = self.sitting_sample_gate(lean,p)
            bounded_snapshot = self.sitting_evidence.update(t,p,hip,lean,thigh,ankle,seated_pose,c.stable_speed)
            baseline_pose = seated_pose and v is not None and abs(v)<=c.stable_speed
            if baseline_pose:
                self.sitting_samples.append((t, float(hip), float(lean), float(thigh), float(ankle)))
                while self.sitting_samples and t-self.sitting_samples[0][0]>c.sitting_window+1e-9:
                    self.sitting_samples.popleft()
                if len(self.sitting_samples)>=3 and t-self.sitting_samples[0][0]>=c.sitting_window*.8-1e-9:
                    h,l,th,an=[median(x[i] for x in self.sitting_samples) for i in range(1,5)]
                    self.sitting_source='short_speed'
                    self.sitting_details={'hip':h,'lean':l,'thigh':th,'ankle':an}
                    self.last_sitting_t=t
                    self.sitting_history={'time':float(t),'measurement':dict(self.sitting_details)}
                    self.last_sitting=self.sitting_matches(h,l,th,an)
            else:
                self.sitting_samples.clear()
            if bounded_snapshot is not None and self.last_sitting_t != t:
                self.sitting_source='bounded_window'
                self.sitting_details=bounded_snapshot
                self.last_sitting_t=t
                self.sitting_history={'time':float(t),'measurement':dict(bounded_snapshot)}
                h,l,th,an=[bounded_snapshot[k] for k in ('hip','lean','thigh','ankle')]
                self.last_sitting=self.sitting_matches(h,l,th,an)
            # Upright, stable samples during preparation can form a NEW
            # baseline before a rise. Never reuse a moving/leaning frame.
            if self.state == 'PERSIAPAN' and self.last_sitting_t == t:
                self.initial_sitting_source = self.sitting_source
                self.initial_sitting = self.last_sitting
                self.initial_sitting_t = self.last_sitting_t
                self.initial_sitting_details = dict(self.sitting_details)
        if self.state == 'DUDUK':
            # Counting needs an observed seated origin, not a passing posture score.
            seated = p<=c.seated_progress and self.seated_geometry(hip)
            if self.held('seat_seen', seated, t): self.seated_anchor_t=t
            anchor_fresh = self.seated_anchor_t is not None and 0<=t-self.seated_anchor_t<=c.seated_evidence_max_age
            ready = self.sitting_matches(hip,lean,thigh,ankle)
            # A speed/8% candidate must also leave the seated height band.
            # Low/no lean still does not prevent counting a visible rise.
            if anchor_fresh and self.held('count_rise', self.rise_threshold is not None and v is not None and v>self.rise_threshold and p>.08, t) and p>c.seated_progress:
                self.begin_attempt(self.since['count_rise'], lean, hand, 'BANGKIT')
                return 'Bangkit terdeteksi; asesmen duduk mengikuti ketersediaan data'
            if anchor_fresh and self.held('onset', p < .4 and lean > self.preparation_threshold(), t):
                self.begin_attempt(self.since['onset'], lean, hand, 'PERSIAPAN')
                return 'Persiapan: condong terdeteksi; menunggu kenaikan pinggul'
            if self.last_sitting is None:
                return 'Duduk diam untuk asesmen; gerak tetap dapat dihitung dari duduk teramati'
            return 'Posisi awal sesuai; mulai condong' if ready else 'Sesuaikan posisi duduk: badan tegak, paha mendatar, kaki di bawah lutut'
        if self.state in ('PERSIAPAN', 'BANGKIT'):
            # Hands near a vertical thigh on a standing plateau are not an
            # indication of hand assistance during rising.
            hand_relevant = warning_context(self.state,p,hip,knee,c.stand_progress,c.straight_tolerance)
            self.hand_hint |= hand and hand_relevant
            if self.state == 'PERSIAPAN':
                self.peak = max(self.peak, lean)
                if self.held('rise', self.rise_threshold is not None and v is not None and v > self.rise_threshold and p > .08, t) and p>c.seated_progress:
                    self.on_rise_started(self.since['rise'])
                    self.state = 'BANGKIT'
                    self.rise_attempts += 1
                    self.since.clear()
                elif self.held('cancel', lean <= self.lean_base+3 and p < .1 and self.seated_geometry(hip), t):
                    self.discard_preparation(t)
                    return 'Persiapan dibatalkan; belum ada bangkit terdeteksi'
                return 'Kemiringan minimum terpenuhi' if self.peak >= c.lean_min else 'Condongkan badan lebih ke depan'
            hip_target,knee_target=self.standing_targets()
            self.standing_checks={'height':bool(p>=c.stand_progress),'hip':bool(hip>=hip_target),'knee':bool(knee>=knee_target)}
            geometry_ok=all(self.standing_checks.values())
            plateau_stable=self.standing_filter.update(t,p,geometry_ok,c.stable_speed)
            # Fast stopping keeps the existing short-window path. A sustained
            # bounded plateau can also confirm stability when local slopes
            # jitter. Geometry and the continuous hold remain mandatory.
            short_stable=v is not None and abs(v)<=c.stable_speed
            stable=short_stable or plateau_stable
            self.stability_details={'short_speed':v,'short_stable':bool(short_stable),
                'window_speed':self.standing_filter.speed,
                'window_excursion':self.standing_filter.excursion,
                'window_span':self.standing_filter.span,
                'plateau_stable':bool(plateau_stable),
                'source':('short+plateau' if short_stable and plateau_stable else
                          'short' if short_stable else 'plateau' if plateau_stable else 'waiting')}
            self.standing_checks['speed']=stable
            standing=all(self.standing_checks.values())
            for name, passed in self.standing_checks.items():
                if not passed:self.standing_blockers[name]=self.standing_blockers.get(name,0)+1
            if standing:
                self.best_standing_hold=max(self.best_standing_hold,t-self.since.get('stand',t))
            if self.held('stand', standing, t):
                end = self.since['stand']
                self.finish(end, True)
                return 'Bangkit lengkap terdeteksi'
            if self.held('failed', p < c.seated_progress and lean <= self.lean_base+10, t):
                self.returned_attempts += 1
                self.finish(t, False)
                return ('Berdiri belum terkonfirmasi: data terputus' if self.results[-1]['bangkit_lengkap'] is None else 'Syarat berdiri lengkap belum terpenuhi')
            blocked=', '.join(k for k,ok in self.standing_checks.items() if not ok)
            return 'Berdiri: menunggu '+(blocked or 'stabil 0.3 detik')
        if self.held('return', p <= c.seated_progress and self.seated_geometry(hip), t):
            self.sitting_samples.clear()
            self.sitting_evidence.clear()
            self.cycles += 1
            self.returned_attempts += 1
            self.state = 'DUDUK'
            self.since.clear()
            return 'Siklus selesai; siap latihan berikutnya'
        return 'Berdiri lengkap; kembali duduk untuk siklus berikutnya'

    def discard_preparation(self, t):
        # No confirmed rise: preparation is not a completed STS attempt.
        # Restore only the same recent, uninterrupted snapshot. Keep its original
        # timestamp: repeated preparation must never extend its lifetime.
        fresh = (not self.observation_missing and
                 self.initial_sitting_t is not None and
                 0 <= t-self.initial_sitting_t <= self.cfg.seated_evidence_max_age)
        saved = self.initial_sitting if fresh else None
        saved_t = self.initial_sitting_t if fresh else None
        details = dict(self.initial_sitting_details) if fresh else {}
        # These samples already passed the unchanged baseline gate. Retain a
        # partial window across cancellation; update() still prunes by time.
        if self.observation_missing:
            self.sitting_samples.clear()
        self.state = 'DUDUK'
        self.start = None
        self.initial_sitting = None
        self.initial_sitting_t = None
        self.initial_sitting_details = {}
        self.observation_missing = False
        self.last_sitting = saved
        self.last_sitting_t = saved_t
        self.sitting_details = details
        # The cancel hold itself observes a seated posture; count origin is
        # independent of the quality snapshot and still needs a real rise.
        self.seated_anchor_t = t
        self.since.clear()

    def assessment_text(self):
        if not self.results:
            return "Hasil terakhir: belum ada percobaan selesai"
        r = self.results[-1]
        sit = "?" if r["duduk_awal_sesuai"] is None else ("YA" if r["duduk_awal_sesuai"] else "BELUM")
        a = "?" if r["bangkit_lengkap"] is None else ("YA" if r["bangkit_lengkap"] else "BELUM")
        b = "?" if r["penilaian_tahap"]["condong"]["memenuhi"] is None else ("YA" if r["minimum_terpenuhi"] else "BELUM")
        label = {'MEMENUHI':'MEMENUHI','BELUM MEMENUHI':'BELUM MEMENUHI','BELUM DAPAT DINILAI':'DATA KURANG'}[r['status_sts']]
        return f"Terakhir: Duduk {sit} | Condong {b} | Berdiri {a} | STS: {label}"

    def finish(self, t, success):
        confirmed = bool(success)
        # Lack of standing evidence during a gap is not proof of failure.
        standing_unknown = not confirmed and (self.observation_missing or success is None)
        success = None if standing_unknown else confirmed
        standing_status = 'TERKONFIRMASI' if confirmed else ('BELUM DAPAT DIKONFIRMASI' if standing_unknown else 'BELUM LENGKAP')
        standing_message = ('Berdiri lengkap terkonfirmasi' if confirmed else
            ('Bangkit teramati; berdiri lengkap belum dapat dikonfirmasi karena data terputus' if standing_unknown else 'Bangkit teramati; syarat berdiri lengkap belum terpenuhi'))
        if self.initial_sitting is not None:
            self.initial_sitting = bool(self.initial_sitting)
        self.hand_hint = bool(self.hand_hint)
        criteria = [self.initial_sitting, self.peak >= self.cfg.lean_min, success]
        status = 'BELUM DAPAT DINILAI' if self.observation_missing or standing_unknown or self.initial_sitting is None else ('MEMENUHI' if all(criteria) else 'BELUM MEMENUHI')
        reasons = []
        if self.initial_sitting is None: reasons.append('Data duduk awal belum tersedia')
        if self.initial_sitting is False: reasons.append('Posisi duduk awal belum sesuai')
        if not criteria[1]: reasons.append('Kemiringan minimum belum terpenuhi')
        if not confirmed: reasons.append(standing_message)
        if self.observation_missing: reasons.append('Pengamatan terputus selama percobaan')
        report = self.make_report(success)
        self.results.append(dict(duduk_awal_metode=self.initial_sitting_source,penilaian_tahap=report, acuan=getattr(self,"reference_label","Aturan operasional PDF; toleransi sementara pada config"), bantuan_tangan_dinilai=False, start_time=float(self.start), end_time=float(t), status_berdiri=standing_status, pesan_berdiri=standing_message, duduk_awal_waktu=self.initial_sitting_t, duduk_terakhir_riwayat=self.sitting_history, duduk_awal_pengukuran=dict(self.initial_sitting_details), berdiri_diagnostik={"last_checks":dict(self.standing_checks),"blocked_frame_counts":dict(self.standing_blockers),"best_hold_seconds":float(self.best_standing_hold),"stability":dict(self.stability_details)}, duduk_awal_sesuai=self.initial_sitting, status_sts=status, alasan=reasons, sts_memenuhi=(all(criteria) if status != 'BELUM DAPAT DINILAI' else None), kedua_kriteria_terpenuhi=(None if standing_unknown else bool(success and self.peak >= self.cfg.lean_min)), bangkit_lengkap=success, kemiringan_puncak=round(float(self.peak), 2), minimum_terpenuhi=bool(self.peak >= self.cfg.lean_min), durasi=round(float(t-self.start), 2), indikasi_tangan=self.hand_hint))
        self.complete += int(confirmed)
        self.last_sitting = None
        self.last_sitting_t = None
        self.seated_anchor_t = None
        self.sitting_samples.clear()
        self.sitting_evidence.clear()
        self.state = 'BERDIRI' if success else 'DUDUK'
        self.since.clear()
