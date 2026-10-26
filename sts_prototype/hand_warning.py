"""Left-hand/thigh proximity in image pixels, not contact or weight bearing.

Independent from the ankle/body gate. Unknown input clears temporal evidence.
Thresholds are prototype settings, not validated contact detection criteria.
"""
import math
from signals import MAX_SAMPLE_GAP

HAND_POINTS = {15: 'wrist', 17: 'pinky', 19: 'index', 21: 'thumb'}


def warning_context(state, p, hip, knee, stand_progress=.9, straight_tolerance=15.):
    if state not in ('PERSIAPAN', 'BANGKIT'):
        return False
    if not all(math.isfinite(float(x)) for x in (p, hip, knee)):
        return False
    # Suppress on an upright plateau even while BANGKIT is waiting for speed.
    upright = p >= stand_progress and hip >= 180-straight_tolerance and knee >= 180-straight_tolerance
    return not upright


def hand_measure(result, width, height, threshold=.12, visibility=.65):
    out = {'hand_raw': None, 'hand_distance': None, 'hand_point': None,
           'hand_threshold': threshold, 'hand_reason': 'pose_missing'}
    for name in HAND_POINTS.values():
        out['hand_visibility_'+name] = None
        out['hand_distance_'+name] = None
    if not result.pose_landmarks:
        return out
    lm = result.pose_landmarks.landmark
    for i, name in HAND_POINTS.items():
        out['hand_visibility_'+name] = float(lm[i].visibility)
    def valid(i):
        return all(math.isfinite(float(v)) for v in (lm[i].x, lm[i].y, lm[i].visibility)) and lm[i].visibility >= visibility
    def point(i):
        return (float(lm[i].x)*width, float(lm[i].y)*height)
    if not all(valid(i) for i in (11, 23, 25)):
        out['hand_reason'] = 'shoulder_hip_knee_unreliable'
        return out
    shoulder, hip, knee = (point(i) for i in (11, 23, 25))
    torso = math.dist(shoulder, hip)
    seg = (knee[0]-hip[0], knee[1]-hip[1])
    den = seg[0]**2+seg[1]**2
    if torso < 10 or den < 1:
        out['hand_reason'] = 'degenerate_geometry'
        return out
    distances = []
    for i, name in HAND_POINTS.items():
        if not valid(i):
            continue
        x, y = point(i)
        u = min(1., max(0., ((x-hip[0])*seg[0]+(y-hip[1])*seg[1])/den))
        distance = math.dist((x, y), (hip[0]+u*seg[0], hip[1]+u*seg[1]))/torso
        out['hand_distance_'+name] = distance
        distances.append((distance, name))
    if not distances:
        out['hand_reason'] = 'hand_unreliable'
        return out
    distance, name = min(distances)
    out.update(hand_raw=distance < threshold, hand_distance=distance,
               hand_point=name, hand_reason='ok')
    return out


class HandWarning:
    def __init__(self, on_seconds=.15, off_seconds=.2):
        self.on_seconds, self.off_seconds = on_seconds, off_seconds
        self.reset()

    def reset(self):
        self.last_t = self.since = self.candidate = None
        self.active = None

    def update(self, t, raw):
        if self.last_t is not None and (t <= self.last_t or t-self.last_t > MAX_SAMPLE_GAP):
            self.reset()
        self.last_t = t
        if raw is None:
            self.since = self.candidate = self.active = None
            return None
        raw = bool(raw)
        if self.candidate is None or raw != self.candidate:
            self.candidate, self.since = raw, t
        delay = self.on_seconds if raw else self.off_seconds
        if t-self.since >= delay-1e-9:
            self.active = raw
        return self.active
