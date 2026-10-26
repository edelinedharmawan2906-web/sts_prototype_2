"""All AWS calls are intercepted by moto; no real table/credentials needed."""
import json
import unittest
from unittest.mock import patch
import boto3
from moto import mock_aws
from cloud_sessions import DynamoSessions, Conflict, NotFound, Expired
from session_core import Session, NewSession, Frame
from serverless_state import restore
from demo_data import landmarks


class CloudSessionTests(unittest.TestCase):
    def setUp(self):
        self.mock = mock_aws()
        self.mock.start()
        self.addCleanup(self.mock.stop)
        self.now = 1000
        self.client = boto3.client('dynamodb', region_name='ap-southeast-2',
            aws_access_key_id='testing', aws_secret_access_key='testing')
        self.client.create_table(TableName='sts-test', BillingMode='PAY_PER_REQUEST',
            KeySchema=[dict(AttributeName='pk', KeyType='HASH'), dict(AttributeName='sk', KeyType='RANGE')],
            AttributeDefinitions=[dict(AttributeName='pk', AttributeType='S'),
                                  dict(AttributeName='sk', AttributeType='S')])
        self.store = DynamoSessions(self.client, 'sts-test', clock=lambda: self.now)
        self.initial = self.store.create('user-a', {}, 'create-1')
        self.sid = self.initial['session_id']

    def test_create_and_frame_retry_across_new_adapter_instances(self):
        self.assertEqual(self.store.create('user-a', {}, 'create-1'), self.initial)
        with self.assertRaises(Conflict):
            self.store.create('user-a', {'width':800}, 'create-1')
        batch = [dict(t=0, landmarks=landmarks()), dict(t=.05, landmarks=landmarks())]
        result = self.store.apply('user-a', self.sid, 'frames-1', 0, 'frames', batch)
        fresh = DynamoSessions(self.client, 'sts-test', clock=lambda: self.now)
        self.assertEqual(fresh.apply('user-a', self.sid, 'frames-1', 0, 'frames', batch), result)
        self.assertEqual(fresh.status('user-a', self.sid)['version'], 1)
        history = fresh.history('user-a', self.sid)
        self.assertEqual(len(history), 1)
        self.assertEqual(len(history[0]['frames']), 2)
        _, count = restore(fresh._session('user-a', self.sid)['checkpoint'])
        self.assertEqual(count, 2)
        with self.assertRaises(Conflict):
            fresh.apply('user-a', self.sid, 'frames-1', 0, 'frames', [dict(t=2)])
        # An old replay still returns its original response after a newer commit.
        fresh.apply('user-a', self.sid, 'frames-2', 1, 'frames', [dict(t=.1)])
        self.assertEqual(fresh.apply('user-a', self.sid, 'frames-1', 0, 'frames', batch), result)

    def test_owner_expiry_and_closed_session_checks(self):
        with self.assertRaises(NotFound):
            self.store.status('user-b', self.sid)
        with self.assertRaises(NotFound):
            self.store.apply('user-b', self.sid, 'bad', 0, 'frames', [dict(t=0)])
        finished = self.store.apply('user-a', self.sid, 'finish-1', 0, 'finish', {})
        self.assertTrue(finished['closed'])
        self.assertEqual(self.store.apply('user-a', self.sid, 'finish-1', 0, 'finish', {}), finished)
        with self.assertRaises(Conflict):
            self.store.apply('user-a', self.sid, 'after-finish', 1, 'frames', [dict(t=0)])
        self.now += 8*86400
        with self.assertRaises(Expired):
            self.store.status('user-a', self.sid)

    def test_failed_batch_and_stale_version_leave_no_extra_history(self):
        with self.assertRaises(ValueError):
            self.store.apply('user-a', self.sid, 'invalid', 0, 'frames', [dict(t=1), dict(t=0)])
        self.assertEqual(self.store.status('user-a', self.sid)['version'], 0)
        self.assertEqual(self.store.history('user-a', self.sid), [])
        self.store.apply('user-a', self.sid, 'valid', 0, 'frames', [dict(t=0)])
        with self.assertRaises(Conflict):
            self.store.apply('user-a', self.sid, 'stale', 0, 'frames', [dict(t=.05)])
        self.assertEqual(len(self.store.history('user-a', self.sid)), 1)

    def test_competing_commit_is_atomic_and_cannot_overwrite(self):
        transaction = self.client.transact_write_items
        fired = False
        def race(**kwargs):
            nonlocal fired
            if not fired:
                fired = True
                self.store.apply('user-a', self.sid, 'winner', 0, 'frames', [dict(t=0)])
            return transaction(**kwargs)
        with patch.object(self.client, 'transact_write_items', side_effect=race):
            with self.assertRaises(Conflict):
                self.store.apply('user-a', self.sid, 'loser', 0, 'frames', [dict(t=.1)])
        self.assertEqual(self.store.status('user-a', self.sid)['version'], 1)
        self.assertIsNone(self.store._get(self.sid, 'REQUEST#loser'))
        history = self.store.history('user-a', self.sid)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['frames'][0]['t'], 0)

    def test_large_item_rejected_and_no_aws_side_effect_on_import(self):
        with self.assertRaises(ValueError):
            self.store._encode(dict(data='x'*(351*1024)))
        # A fresh module import must never create a client or a table.
        import runpy, cloud_sessions
        with patch.object(boto3, 'client', side_effect=AssertionError('unexpected client')):
            runpy.run_path(cloud_sessions.__file__)

    def test_full_calibrated_cycle_across_persisted_batches(self):
        sid = self.store.create('user-a', {'input_source':'simulation'}, 'demo')['session_id']
        local = Session(NewSession(input_source='simulation'))
        version, request_number, t = 0, 0, 0.
        latest = None
        def apply(operation, body):
            nonlocal version, request_number, latest
            request_number += 1
            latest = self.store.apply('user-a', sid, str(request_number), version, operation, body)
            version = latest['version']
        def capture(posture):
            local.pending = dict(posture=posture, delay=0, deadline=None)
            local.samples = []
            apply('calibration', dict(posture=posture, delay=0))
        def segment(n, progress, lean=0):
            nonlocal t
            batch = []
            for i in range(n):
                p = progress(i/(n-1)) if callable(progress) else progress
                raw = dict(t=round(t, 6), landmarks=landmarks(p, lean))
                local.ingest(Frame.model_validate(raw))
                batch.append(raw); t += .05
                if len(batch) == 7 or i == n-1:
                    apply('frames', batch)
                    actual = {k:v for k,v in latest.items() if k not in ('version','session_id')}
                    self.assertEqual(actual, local.response())
                    batch = []
        capture('duduk'); segment(55, 0); segment(45, 1)
        capture('berdiri'); segment(55, 1); segment(50, 0); segment(20, 0, 28)
        segment(35, lambda p:p, 28); segment(50, 1)
        segment(35, lambda p:1-p); segment(45, 0)
        self.assertEqual((latest['complete'], latest['cycles']), (1, 1))
        rows = [row for batch in self.store.history('user-a', sid) for row in batch['frames']]
        self.assertEqual(rows, local.rows)
        self.assertEqual(len(rows), 390)


if __name__ == '__main__':
    unittest.main()
