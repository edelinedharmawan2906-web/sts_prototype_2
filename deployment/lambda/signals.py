from collections import deque

MAX_SAMPLE_GAP = .3
MAX_SPEED_WINDOW = .6

class WindowSpeed:
    """Causal slope; retain at least three recent samples within a bounded window."""
    def __init__(self, seconds=.2):
        self.seconds=seconds
        self.samples=deque()
    def clear(self): self.samples.clear()
    def update(self,t,p):
        if self.samples and (t<=self.samples[-1][0] or t-self.samples[-1][0]>MAX_SAMPLE_GAP):
            self.clear()
        self.samples.append((float(t),float(p)))
        while len(self.samples)>3 and t-self.samples[0][0]>self.seconds+1e-9:
            self.samples.popleft()
        while self.samples and t-self.samples[0][0]>max(self.seconds,MAX_SPEED_WINDOW)+1e-9:
            self.samples.popleft()
        if len(self.samples)<3 or t-self.samples[0][0]<self.seconds*.5-1e-9:
            return None
        origin=self.samples[0][0]
        xs=[a-origin for a,b in self.samples];ys=[b for a,b in self.samples]
        xm=sum(xs)/len(xs);ym=sum(ys)/len(ys)
        den=sum((x-xm)**2 for x in xs)
        return sum((x-xm)*(y-ym) for x,y in zip(xs,ys))/den if den>1e-12 else None
