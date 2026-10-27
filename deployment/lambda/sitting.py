"""Bounded seated window, independent of instantaneous velocity jitter."""
from collections import deque
from statistics import median
from signals import MAX_SAMPLE_GAP


class SittingEvidence:
    def __init__(self, seconds=.5):
        self.seconds=seconds
        self.samples=deque()

    def clear(self):
        self.samples.clear()

    def update(self,t,p,hip,lean,thigh,ankle,eligible,speed_limit):
        if not eligible:
            self.clear()
            return None
        if self.samples and (t<=self.samples[-1][0] or t-self.samples[-1][0]>MAX_SAMPLE_GAP):
            self.clear()
        self.samples.append((t,p,hip,lean,thigh,ankle))
        while self.samples and t-self.samples[0][0]>self.seconds+1e-9:
            self.samples.popleft()
        if len(self.samples)<3 or t-self.samples[0][0]<self.seconds*.8-1e-9:
            return None
        xs=[r[0]-self.samples[0][0] for r in self.samples]
        ys=[r[1] for r in self.samples]
        xm=sum(xs)/len(xs);ym=sum(ys)/len(ys)
        den=sum((x-xm)**2 for x in xs)
        if den<=1e-12:return None
        speed=sum((x-xm)*(y-ym) for x,y in zip(xs,ys))/den
        if abs(speed)>speed_limit or max(ys)-min(ys)>speed_limit*self.seconds:
            return None
        return {name:float(median(r[i] for r in self.samples))
                for name,i in [('hip',2),('lean',3),('thigh',4),('ankle',5)]}
