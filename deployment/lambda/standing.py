"""Causal standing plateau check in normalized seated-to-standing travel.

Only reliable frames satisfying all standing geometry enter this window.
The speed limit is unchanged; excursion also bounds oscillation whose slope
could cancel out. Technical window choices still need independent validation.
"""
from collections import deque
import math
from signals import MAX_SAMPLE_GAP


class StandingStability:
    def __init__(self, window=.5):
        if not math.isfinite(window) or window <= 0:
            raise ValueError('standing_window must be positive and finite')
        self.window = window
        self.samples = deque()
        self.clear()

    def clear(self):
        self.samples.clear()
        self.speed = self.excursion = self.span = None

    def update(self, t, p, geometry_ok, speed_limit):
        if (not geometry_ok or not math.isfinite(t) or not math.isfinite(p)):
            self.clear()
            return False
        if self.samples and (t <= self.samples[-1][0] or t-self.samples[-1][0] > MAX_SAMPLE_GAP):
            self.clear()
        self.samples.append((t, p))
        while self.samples and t-self.samples[0][0] > self.window+1e-9:
            self.samples.popleft()
        self.span = t-self.samples[0][0]
        self.speed = self.excursion = None
        if len(self.samples) < 3 or self.span < .8*self.window-1e-9:
            return False
        origin = self.samples[0][0]
        xs = [x-origin for x, y in self.samples]
        ys = [y for x, y in self.samples]
        xm, ym = sum(xs)/len(xs), sum(ys)/len(ys)
        den = sum((x-xm)**2 for x in xs)
        if den <= 1e-12:
            return False
        self.speed = sum((x-xm)*(y-ym) for x,y in zip(xs,ys))/den
        self.excursion = max(ys)-min(ys)
        return (abs(self.speed) <= speed_limit and
                self.excursion <= speed_limit*self.window)
