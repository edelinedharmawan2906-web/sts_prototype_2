"""Versioned JSON checkpoints for trusted server storage, never client input.

Stage 1 only: no AWS resources, HTTP routes, authentication or database adapter.
Frame history is returned separately and MUST be stored by the future adapter.
"""
from collections import deque
import hashlib
import json
from session_core import Session, NewSession, Frame, ROOT
from engine import Config
from personal_engine import PersonalEngine
from personal_rules import PersonalRules
from signals import WindowSpeed
from sitting import SittingEvidence
from standing import StandingStability

FORMAT = 'sts-checkpoint-v2'
MAX_FRAMES = 36000
FACTORIES = {
    'Config': Config,
    'PersonalRules': PersonalRules,
    'WindowSpeed': WindowSpeed,
    'SittingEvidence': SittingEvidence,
    'StandingStability': StandingStability,
    'PersonalEngine': lambda: PersonalEngine(Config(), PersonalRules()),
}


def _fingerprint():
    # A checkpoint must not silently resume under different posture rules.
    paths = ('config.json', 'personal_rules.json', 'session_core.py', 'engine.py',
             'personal_engine.py', 'signals.py', 'sitting.py', 'standing.py',
             'personal_rules.py', 'measurements.py', 'calibration.py',
             'diagnostics.py', 'assessment.py', 'hand_warning.py', 'serialization.py')
    digest = hashlib.sha256()
    for name in paths:
        digest.update(name.encode())
        digest.update((ROOT / name).read_bytes())
    return digest.hexdigest()


def _pack(value):
    if value is None or type(value) in (bool, int, float, str):
        return value
    if type(value) in (list, tuple, deque):
        return [type(value).__name__, [_pack(v) for v in value]]
    if type(value) is dict:
        if not all(type(k) is str for k in value):
            raise ValueError('Checkpoint dictionary keys must be strings')
        return ['dict', {k: _pack(v) for k, v in value.items()}]
    name = type(value).__name__
    if name in FACTORIES and type(value) is type(FACTORIES[name]()):
        fields = value.model_dump() if isinstance(value, PersonalRules) else vars(value)
        return [name, {k: _pack(v) for k, v in fields.items()}]
    # Measurements can contain numpy scalar bools/floats, never arrays.
    from serialization import json_scalar
    try:
        return _pack(json_scalar(value))
    except TypeError as exc:
        raise ValueError(f'Unsupported checkpoint type: {type(value)}') from exc


def _unpack(value):
    if value is None or type(value) in (bool, int, float, str):
        return value
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError('Invalid checkpoint value')
    kind, fields = value
    if kind in ('list', 'tuple', 'deque'):
        if type(fields) is not list:
            raise ValueError('Invalid checkpoint sequence')
        return {'list': list, 'tuple': tuple, 'deque': deque}[kind](_unpack(v) for v in fields)
    if type(fields) is not dict:
        raise ValueError('Invalid checkpoint fields')
    if kind == 'dict':
        return {k: _unpack(v) for k, v in fields.items()}
    if kind not in FACTORIES:
        raise ValueError('Unknown checkpoint class')
    obj = FACTORIES[kind]()
    expected = set(obj.model_dump() if isinstance(obj, PersonalRules) else vars(obj))
    if set(fields) != expected:
        raise ValueError(f'Checkpoint field mismatch for {kind}')
    decoded = {k: _unpack(v) for k, v in fields.items()}
    if kind == 'PersonalRules':
        return PersonalRules.model_validate(decoded)
    obj.__dict__.update(decoded)
    return obj


def checkpoint(session, frame_count):
    """Exclude the lock and unbounded raw history; persist history separately."""
    if type(frame_count) is not int or not 0 <= frame_count <= MAX_FRAMES:
        raise ValueError('Invalid total frame count')
    fields = {k: v for k, v in vars(session).items() if k not in ('lock', 'rows')}
    payload = dict(format=FORMAT, fingerprint=_fingerprint(),
                   frame_count=frame_count, state=_pack(fields))
    return json.dumps(payload, allow_nan=False, separators=(',', ':'))


def restore(serialized):
    """Only load checkpoints from authenticated backend-owned storage."""
    def reject_constant(value):
        raise ValueError(f'Invalid JSON constant: {value}')
    payload = json.loads(serialized, parse_constant=reject_constant)
    if payload.get('format') != FORMAT or payload.get('fingerprint') != _fingerprint():
        raise ValueError('Checkpoint version/code mismatch; start a new session')
    count = payload.get('frame_count')
    if type(count) is not int or not 0 <= count <= MAX_FRAMES:
        raise ValueError('Invalid total frame count')
    fields = _unpack(payload['state'])
    session = Session(NewSession())
    expected = set(vars(session)) - {'lock', 'rows'}
    if type(fields) is not dict or set(fields) != expected:
        raise ValueError('Checkpoint session fields mismatch')
    session.__dict__.update(fields)
    session.engine.rules = session.rules
    session.rows = []
    return session, count


def process_batch(serialized, raw_frames):
    """All-or-nothing locally; caller must commit state and history atomically.

    Uses capture timestamps, NOT HTTP arrival time. Callers must serialize writes
    per session and implement request idempotency before deploying to AWS.
    """
    if type(raw_frames) is not list or not 1 <= len(raw_frames) <= 30:
        raise ValueError('Batch must contain 1..30 frames')
    frames = [Frame.model_validate(frame) for frame in raw_frames]
    session, count = restore(serialized)
    if session.closed:
        raise ValueError('Session is closed')
    if count + len(frames) > MAX_FRAMES:
        raise ValueError('Session frame limit reached')
    previous = session.last_t
    for frame in frames:
        if previous is not None and frame.t <= previous:
            raise ValueError('Frames must be strictly ordered, without duplicates')
        previous = frame.t
    from serialization import json_scalar
    # Freeze each response; the engine mutates its attempts list later.
    responses = [json.loads(json.dumps(session.ingest(frame), default=json_scalar,
                                      allow_nan=False)) for frame in frames]
    return dict(checkpoint=checkpoint(session, count + len(frames)),
                frames=session.rows, responses=responses)
