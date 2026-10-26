import json
import unittest
from session_core import Session, NewSession, Frame
from demo_data import landmarks
from serialization import json_scalar
from serverless_state import checkpoint, restore, process_batch, MAX_FRAMES


def frozen(value):
    return json.loads(json.dumps(value, default=json_scalar, allow_nan=False))


class CheckpointTests(unittest.TestCase):
    def test_calibration_full_cycle_matches_continuous_for_multiple_batches(self):
        for size in (1, 7, 30):
            with self.subTest(size=size):
                continuous = Session(NewSession(input_source='simulation'))
                remote = Session(NewSession(input_source='simulation'))
                count = 0
                t = 0.
                all_rows = []
                def capture(posture):
                    nonlocal remote
                    for session in (continuous, remote):
                        session.pending = dict(posture=posture, delay=0, deadline=None)
                        session.samples = []
                    remote, _ = restore(checkpoint(remote, count))
                def segment(n, progress, lean=0):
                    nonlocal t, remote, count
                    batch = []
                    expected = []
                    for i in range(n):
                        p = progress(i/(n-1)) if callable(progress) else progress
                        raw = dict(t=round(t, 6), landmarks=landmarks(p, lean))
                        expected.append(frozen(continuous.ingest(Frame.model_validate(raw))))
                        batch.append(raw)
                        t += .05
                        if len(batch) == size or i == n-1:
                            result = process_batch(checkpoint(remote, count), batch)
                            self.assertEqual(result['responses'], expected)
                            all_rows.extend(result['frames'])
                            remote, count = restore(result['checkpoint'])
                            self.assertEqual(frozen(remote.response()), frozen(continuous.response()))
                            self.assertEqual(remote.rows, [])
                            batch, expected = [], []
                capture('duduk'); segment(55, 0)
                self.assertEqual(remote.mode, 'CAL_BERDIRI')
                segment(45, 1); capture('berdiri'); segment(55, 1)
                self.assertIsNotNone(remote.reference_standing)
                segment(50, 0); segment(20, 0, 28)
                segment(35, lambda p: p, 28); segment(50, 1)
                segment(35, lambda p: 1-p); segment(45, 0)
                self.assertEqual((remote.engine.complete, remote.engine.cycles), (1, 1))
                self.assertEqual(frozen(all_rows), frozen(continuous.rows))
                self.assertEqual(count, len(continuous.rows))

    def test_missing_pose_and_time_gap_preserved_after_restore(self):
        direct = Session(NewSession())
        raw = [dict(t=t, landmarks=landmarks() if i % 2 else None)
               for i, t in enumerate((0, .05, .1, 1., 1.05))]
        state = checkpoint(Session(NewSession()), 0)
        for row in raw:
            expected = frozen(direct.ingest(Frame.model_validate(row)))
            result = process_batch(state, [row])
            self.assertEqual(result['responses'][0], expected)
            state = result['checkpoint']

    def test_reject_duplicate_reverse_time_and_batch_without_mutating_checkpoint(self):
        original = checkpoint(Session(NewSession()), 0)
        for batch in ([], [dict(t=1), dict(t=1)], [dict(t=2), dict(t=1)],
                      [dict(t=i) for i in range(31)]):
            with self.assertRaises(ValueError):
                process_batch(original, batch)
            session, count = restore(original)
            self.assertIsNone(session.last_t)
            self.assertEqual(count, 0)

    def test_limit_closed_version_and_invalid_state(self):
        session = Session(NewSession())
        with self.assertRaises(ValueError):
            process_batch(checkpoint(session, MAX_FRAMES), [dict(t=0)])
        session.closed = True
        with self.assertRaises(ValueError):
            process_batch(checkpoint(session, 0), [dict(t=0)])
        payload = json.loads(checkpoint(session, 0))
        payload['fingerprint'] = 'different'
        with self.assertRaises(ValueError):
            restore(json.dumps(payload))
        payload = json.loads(checkpoint(session, 0))
        payload['state'] = ['arbitrary_import', {}]
        with self.assertRaises(ValueError):
            restore(json.dumps(payload))


if __name__ == '__main__':
    unittest.main()
