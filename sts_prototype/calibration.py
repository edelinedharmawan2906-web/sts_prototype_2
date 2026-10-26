import math
import statistics
from signals import WindowSpeed, MAX_SAMPLE_GAP

def speed_stats(samples, rise_pixels, multiplier=3, window=.2):
    """Filtered seated hip y derivatives in normalized rise/second."""
    if rise_pixels <= 0 or len(samples) < 6:
        raise ValueError('Kalibrasi kecepatan membutuhkan minimal 6 sampel dan kenaikan positif')
    velocities=[]
    estimator=WindowSpeed(window)
    for t,m in samples:
        v=estimator.update(t,-float(m['y'])/rise_pixels)
        if v is not None: velocities.append(v)
    if len(velocities)<5 or not all(math.isfinite(v) for v in velocities):
        raise ValueError('Sampel kecepatan kalibrasi tidak valid')
    baseline=statistics.mean(velocities)
    sd=statistics.stdev(velocities)
    # No fixed 0.10 fallback; tiny numerical guard only, not a validated threshold.
    return baseline,sd,max(1e-6,baseline+multiplier*sd)

def collect_calibration(samples, t, measurement, seconds=1):
    """Clear interrupted sample runs; caller keeps calibration armed."""
    if measurement is None:
        samples.clear()
        return False
    if samples and (t<=samples[-1][0] or t-samples[-1][0] > MAX_SAMPLE_GAP):
        samples.clear()
    samples.append((t,measurement.copy()))
    return len(samples)>=9 and t-samples[0][0]>=seconds
