"""Optional temporal angle estimator. Auxiliary state never changes the STS engine.

Capture timestamps in seconds; a 30-sample grid spans 29/30 seconds. No
extrapolation, no cross-gap interpolation, no recurrent state shared by users.
"""
from functools import lru_cache
from pathlib import Path
import hashlib
import json
import logging
import os
import threading

import numpy as np

ROOT = Path(__file__).resolve().parent
SPAN = 29 / 30
MAX_GAP = 0.2  # Technical prototype assumption, not clinical validation.
MIN_SAMPLES = 10
INTERVAL = 0.2
FORMAT = 'sts-lstm-window-v1'
logger = logging.getLogger(__name__)


def enabled():
    return os.getenv('STS_LSTM_ENABLED', '0') == '1'


@lru_cache(maxsize=1)
def model_id():
    digest = hashlib.sha256()
    for name in ('model_quantized.tflite', 'scaler_numeric.json', 'feature_names.json', 'label_names.json'):
        digest.update((ROOT / name).read_bytes())
    return digest.hexdigest()


def empty():
    return {'format': FORMAT, 'model_id': model_id(), 'samples': [], 'latest': None}


def waiting(reason):
    return {'status': reason, 'model': 'LSTM quantized', 'used_for_sts_counts': False}


def public_state(state):
    if not enabled():
        return waiting('disabled')
    if not state:
        return waiting('warming_up')
    return state.get('latest') or waiting('warming_up')


def resample(samples):
    """Return raw 30x132 float64 input, or None until a covered valid window exists."""
    if len(samples) < MIN_SAMPLES:
        return None
    ts = np.asarray([sample['t'] for sample in samples], dtype=np.float64)
    if not np.isfinite(ts).all() or np.any(np.diff(ts) <= 0):
        raise ValueError('Invalid sample timestamps')
    target = ts[-1] - np.arange(29, -1, -1) / 30
    if ts[0] > target[0] + 1e-9 or np.max(np.diff(ts)) > MAX_GAP + 1e-9:
        return None
    values = np.asarray([sample['features'] for sample in samples], dtype=np.float64)
    if values.shape != (len(samples), 132) or not np.isfinite(values).all():
        raise ValueError('Invalid feature window')
    # Every target lies within observed capture times. Never hold an old endpoint.
    return np.column_stack([np.interp(target, ts, values[:, j]) for j in range(132)])


@lru_cache(maxsize=1)
def _runtime():
    from ai_edge_litert.interpreter import Interpreter
    scaler = json.loads((ROOT / 'scaler_numeric.json').read_text())
    mean, scale = np.asarray(scaler['mean']), np.asarray(scaler['scale'])
    if mean.shape != (132,) or scale.shape != (132,) or not np.isfinite(mean).all() or not np.isfinite(scale).all() or np.any(scale <= 0):
        raise ValueError('Invalid scaler')
    names = json.loads((ROOT / 'feature_names.json').read_text())
    # The training metadata must match the standard MediaPipe landmark order.
    base = ['NOSE','LEFT_EYE_INNER','LEFT_EYE','LEFT_EYE_OUTER','RIGHT_EYE_INNER','RIGHT_EYE','RIGHT_EYE_OUTER','LEFT_EAR','RIGHT_EAR','MOUTH_LEFT','MOUTH_RIGHT','LEFT_SHOULDER','RIGHT_SHOULDER','LEFT_ELBOW','RIGHT_ELBOW','LEFT_WRIST','RIGHT_WRIST','LEFT_PINKY','RIGHT_PINKY','LEFT_INDEX','RIGHT_INDEX','LEFT_THUMB','RIGHT_THUMB','LEFT_HIP','RIGHT_HIP','LEFT_KNEE','RIGHT_KNEE','LEFT_ANKLE','RIGHT_ANKLE','LEFT_HEEL','RIGHT_HEEL','LEFT_FOOT_INDEX','RIGHT_FOOT_INDEX']
    if names != [name + '_' + key for name in base for key in ('x','y','z','visibility')]:
        raise ValueError('Feature order mismatch')
    labels = json.loads((ROOT / 'label_names.json').read_text())
    if len(labels) != 39:
        raise ValueError('Label count mismatch')
    it = Interpreter(model_path=str(ROOT / 'model_quantized.tflite'), num_threads=1)
    it.allocate_tensors()
    inp, out = it.get_input_details()[0], it.get_output_details()[0]
    if tuple(inp['shape']) != (1,30,132) or tuple(out['shape']) != (1,39) or inp['dtype'] != np.float32 or out['dtype'] != np.float32:
        raise ValueError('Model contract mismatch')
    return it, inp['index'], out['index'], mean, scale, labels, threading.Lock()


def predict(raw):
    it, inp, out, mean, scale, labels, lock = _runtime()
    with np.errstate(over='raise', invalid='raise'):
        scaled = ((raw - mean) / scale).astype(np.float32)
    if scaled.shape != (30,132) or not np.isfinite(scaled).all():
        raise ValueError('Invalid normalized input')
    with lock:
        it.set_tensor(inp, scaled[np.newaxis])
        it.invoke()
        values = it.get_tensor(out)[0].copy()
    if not np.isfinite(values).all():
        raise ValueError('Non-finite model output')
    return dict(zip(labels, map(float, values)))


def knee_geometry(landmarks, width, height, side):
    indices = (23,25,27) if side == 'left' else (24,26,28)
    if min(landmarks[i]['visibility'] for i in indices) < 0.65:
        return None
    a,b,c = [np.asarray([landmarks[i]['x']*width, landmarks[i]['y']*height]) for i in indices]
    u,v = a-b,c-b
    if min(np.linalg.norm(u),np.linalg.norm(v)) < 1:
        return None
    internal = np.degrees(np.arccos(np.clip(np.dot(u,v)/(np.linalg.norm(u)*np.linalg.norm(v)), -1, 1)))
    return float(180 - internal)


def advance(state, rows, width, height):
    if not enabled():
        for row in rows:
            row['lstm'] = waiting('disabled')
        return None
    if not state or state.get('format') != FORMAT or state.get('model_id') != model_id():
        state = empty()
    for row in rows:
        samples = state['samples']
        landmarks, t = row.get('landmarks'), row['t']
        valid = (isinstance(landmarks, list) and len(landmarks) == 33
                 and row.get('quality', {}).get('accepted') is True)
        if not valid:
            state['samples'] = []
            state['latest'] = waiting('pose_missing')
            row['lstm'] = dict(state['latest'])
            continue
        if samples and t - samples[-1]['t'] > MAX_GAP + 1e-9:
            samples = []
            state['latest'] = waiting('frame_gap')
        vector = [lm[key] for lm in landmarks for key in ('x','y','z','visibility')]
        samples.append({'t': t, 'features': vector})
        # Preserve one point before the oldest target, for interpolation.
        while len(samples) > 2 and samples[1]['t'] <= t - SPAN:
            samples.pop(0)
        state['samples'] = samples[-64:]
        previous = state.get('latest') or {}
        if previous.get('status') == 'ready' and t - previous['t'] < INTERVAL - 1e-9:
            row['lstm'] = dict(previous)
            continue
        raw = resample(state['samples'])
        if raw is None:
            state['latest'] = waiting('warming_up')
        else:
            output = predict(raw)
            geometry = {side: knee_geometry(landmarks, width, height, side) for side in ('left','right')}
            # Do not display a side whose landmarks were poorly visible in the window.
            knees = {}
            for side, ids, label in [('left',(23,25,27),'gt_knee_angle_l'), ('right',(24,26,28),'gt_knee_angle_r')]:
                visible = min(s['features'][i*4+3] for s in state['samples'] for i in ids) >= 0.65
                knees[side] = output[label] if visible and geometry[side] is not None else None
            state['latest'] = {
                'status':'ready','t':t,'window_start':t-SPAN,'window_seconds':SPAN,
                'source_samples':len(state['samples']),'target_samples':30,
                'model':'LSTM quantized','model_id':model_id(),
                'knee_flexion_deg':knees,'geometry_knee_flexion_deg':geometry,
                'outputs':output,'used_for_sts_counts':False,
            }
        row['lstm'] = dict(state['latest'])
    return state


def analyze(state, rows, width, height):
    """LSTM failures must not interrupt the working geometry/counting path."""
    try:
        return advance(state, rows, width, height)
    except Exception as exc:
        logger.warning('STS LSTM unavailable: %s', type(exc).__name__)
        for row in rows:
            row['lstm'] = waiting('inference_error')
        return {'format':FORMAT, 'model_id':None, 'samples':[], 'latest':waiting('inference_error')}


def self_test():
    with np.load(ROOT / 'aws_parity_fixture.npz', allow_pickle=False) as f:
        outputs = np.asarray([list(predict(raw).values()) for raw in f['input_raw']])
        difference = float(np.max(np.abs(outputs - f['expected_quantized'])))
    return {'status':'ok' if difference <= 0.01 else 'mismatch',
            'sample_count':9, 'max_abs_output_difference':difference,
            'enabled':enabled(), 'model_id':model_id(), 'used_for_sts_counts':False}
