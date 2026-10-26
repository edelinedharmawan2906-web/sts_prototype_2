"""Shared original v0.5.6 geometry; no camera or MediaPipe dependency."""
import math
import numpy as np

def angle(a,b,c):
    u,v = a-b,c-b
    den=np.linalg.norm(u)*np.linalg.norm(v)
    if den < 1e-8: raise ValueError('Degenerate landmarks')
    return math.degrees(math.acos(float(np.clip(np.dot(u,v)/den,-1,1))))

def measure(result,w,h,hand=False):
    if not result.pose_landmarks: return None
    lm=result.pose_landmarks.landmark
    side=[11,23,25,27,15]  # Fixed anatomical left side; camera on left.
    if min(lm[i].visibility for i in side[:4]) < .65: return None
    s,hip,k,a=[np.array([lm[i].x*w,lm[i].y*h]) for i in side[:4]]
    torso=np.linalg.norm(s-hip)
    if torso < 10 or np.linalg.norm(k-hip)<1 or np.linalg.norm(a-k)<1: return None
    lean=math.degrees(math.atan2(abs(s[0]-hip[0]),hip[1]-s[1]))
    thigh=math.degrees(math.atan2(abs(k[1]-hip[1]),abs(k[0]-hip[0])))
    ankle=abs(a[0]-k[0])/torso
    return dict(y=float(hip[1]), lean=lean, hip=angle(s,hip,k), knee=angle(hip,k,a), thigh=thigh, ankle=ankle, hand=bool(hand))
