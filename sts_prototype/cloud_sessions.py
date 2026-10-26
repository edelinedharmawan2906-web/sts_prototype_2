"""DynamoDB session adapter. No clients/resources are created on import.

Stage 2: call only from trusted backend code after authenticating the user.
This is not an HTTP handler; never accept an unverified owner from a browser.
"""
import hashlib
import json
import re
import time
from boto3.dynamodb.types import TypeSerializer, TypeDeserializer
from botocore.exceptions import ClientError
from session_core import Session, NewSession, Capture
from serverless_state import checkpoint, restore, process_batch
from serialization import json_scalar


class Conflict(ValueError):
    pass


class NotFound(ValueError):
    pass


class Expired(ValueError):
    pass


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False, default=json_scalar)


def _digest(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value):
        raise ValueError('Request/session ID must be 1..64 letters, digits, - or _')
    return value


def _owner(value):
    if not isinstance(value, str) or not value or len(value.encode()) > 512:
        raise ValueError('Verified owner identity is required')
    return value


class DynamoSessions:
    def __init__(self, client, table_name, *, clock=time.time, retention_seconds=7*86400):
        if type(retention_seconds) is not int or retention_seconds < 60:
            raise ValueError('Retention must be an integer >=60 seconds')
        self.client, self.table = client, table_name
        self.clock, self.retention = clock, retention_seconds
        self.serializer, self.deserializer = TypeSerializer(), TypeDeserializer()

    def _encode(self, item):
        # Conservative cap, leaving room below DynamoDB's 400 KiB item limit.
        # All items below use only flat string/integer attributes.
        if len(_json(item).encode()) > 350*1024:
            raise ValueError('Session/batch too large; archive or reduce the batch')
        return {k: self.serializer.serialize(v) for k, v in item.items()}

    def _get(self, sid, sk):
        result = self.client.get_item(TableName=self.table, ConsistentRead=True,
            Key=self._encode(dict(pk='SESSION#'+_id(sid), sk=sk)))
        if 'Item' not in result:
            return None
        return {k: self.deserializer.deserialize(v) for k, v in result['Item'].items()}

    def _session(self, owner, sid):
        _owner(owner)
        item = self._get(sid, 'STATE')
        if item is None or item['owner'] != owner:
            raise NotFound('Session not found')
        if int(item['expires_at']) <= int(self.clock()):
            raise Expired('Session expired')
        return item

    def create(self, owner, body, creation_id):
        """Stable caller creation ID makes a lost create-response retry safe."""
        _owner(owner); _id(creation_id)
        dimensions = NewSession.model_validate(body)
        sid = _digest([owner, creation_id])[:32]
        session = Session(dimensions)
        response = dict(session_id=sid, version=0, **session.response())
        item = dict(pk='SESSION#'+sid, sk='STATE', owner=owner, version=0,
                    expires_at=int(self.clock())+self.retention,
                    checkpoint=checkpoint(session, 0),
                    create_digest=_digest(dimensions.model_dump()),
                    create_response=_json(response))
        try:
            self.client.put_item(TableName=self.table, Item=self._encode(item),
                                 ConditionExpression='attribute_not_exists(pk)')
        except ClientError as exc:
            if exc.response['Error']['Code'] != 'ConditionalCheckFailedException':
                raise
            existing = self._session(owner, sid)
            if existing['create_digest'] != item['create_digest']:
                raise Conflict('Creation ID already used with different dimensions') from exc
            return json.loads(existing['create_response'])
        return response

    def status(self, owner, sid):
        item = self._session(owner, sid)
        session, _ = restore(item['checkpoint'])
        return dict(session_id=sid, version=int(item['version']), **session.response())

    def _receipt(self, owner, sid, request_id, digest):
        receipt = self._get(sid, 'REQUEST#'+_id(request_id))
        if receipt is None:
            return None
        if receipt['owner'] != owner:
            raise NotFound('Session not found')
        if int(receipt['expires_at']) <= int(self.clock()):
            raise Expired('Request expired')
        if receipt['digest'] != digest:
            raise Conflict('Request ID already used with different contents/version')
        return json.loads(receipt['response'])

    def apply(self, owner, sid, request_id, expected_version, operation, body):
        """Atomic state + frame history + retry receipt, serialized by version.

        Response-loss retry MUST reuse request ID, version and payload. After a
        conflict, refresh status; do not blindly retry old work with a new ID.
        """
        _owner(owner); _id(sid); _id(request_id)
        if type(expected_version) is not int or expected_version < 0:
            raise ValueError('Nonnegative integer expected_version required')
        digest = _digest([operation, expected_version, body])
        item = self._session(owner, sid)
        replay = self._receipt(owner, sid, request_id, digest)
        if replay is not None:
            return replay
        if int(item['version']) != expected_version:
            raise Conflict('Session changed; refresh version before next request')
        session, count = restore(item['checkpoint'])
        if session.closed:
            raise Conflict('Session already finished')
        rows = []
        if operation == 'frames':
            batch = process_batch(item['checkpoint'], body)
            serialized, rows = batch['checkpoint'], batch['frames']
            result = batch['responses'][-1]
        elif operation == 'calibration':
            capture = Capture.model_validate(body)
            expected_mode = 'CAL_DUDUK' if capture.posture == 'duduk' else 'CAL_BERDIRI'
            if session.mode != expected_mode or session.pending:
                raise Conflict('Calibration out of order')
            session.pending = dict(posture=capture.posture, delay=capture.delay, deadline=None)
            session.samples = []
            serialized, result = checkpoint(session, count), session.response()
        elif operation == 'finish':
            if body != {}:
                raise ValueError('Finish body must be {}')
            if session.engine.state == 'BANGKIT':
                session.engine.observation_missing = True
                session.engine.finish(session.last_t or 0, False)
            session.closed = True
            serialized, result = checkpoint(session, count), session.response()
        else:
            raise ValueError('Unknown session operation')
        version = expected_version + 1
        response = dict(session_id=sid, version=version, **result)
        updated = dict(item, checkpoint=serialized, version=version,
                       expires_at=int(item['expires_at']))
        common = dict(pk=item['pk'], owner=owner, expires_at=int(item['expires_at']))
        receipt = dict(common, sk='REQUEST#'+request_id,
                       digest=digest, response=_json(response))
        history = dict(common, sk=f'HISTORY#{version:010d}',
                       version=version, operation=operation, frames=_json(rows))
        writes = [dict(Put=dict(TableName=self.table, Item=self._encode(updated),
                      ConditionExpression='#v = :old AND #o = :owner AND expires_at > :now',
                      ExpressionAttributeNames={'#v': 'version', '#o': 'owner'},
                      ExpressionAttributeValues=self._encode({':old': expected_version,
                          ':owner': owner, ':now': int(self.clock())})))]
        for record in (receipt, history):
            writes.append(dict(Put=dict(TableName=self.table, Item=self._encode(record),
                                       ConditionExpression='attribute_not_exists(pk)')))
        try:
            self.client.transact_write_items(TransactItems=writes)
        except ClientError as exc:
            if exc.response['Error']['Code'] != 'TransactionCanceledException':
                raise
            reasons = exc.response.get('CancellationReasons', [])
            # Propagate capacity/storage/validation failures; don't call them version conflicts.
            if not any(r.get('Code') in ('ConditionalCheckFailed', 'TransactionConflict') for r in reasons):
                raise
            replay = self._receipt(owner, sid, request_id, digest)
            if replay is not None:
                return replay
            raise Conflict('Concurrent session update; refresh session status') from exc
        # Future MQTT/outbox integration must use committed version as event ID.
        # This adapter does not publish, so replay cannot duplicate MQTT effects.
        return json.loads(_json(response))

    def history(self, owner, sid):
        """Read bounded, ordered history; query all pages, not just first 1 MiB."""
        self._session(owner, sid)
        args = dict(TableName=self.table, ConsistentRead=True,
                    KeyConditionExpression='pk = :pk AND begins_with(sk, :prefix)',
                    ExpressionAttributeValues=self._encode({':pk': 'SESSION#'+sid, ':prefix': 'HISTORY#'}))
        batches = []
        while True:
            page = self.client.query(**args)
            for raw in page.get('Items', []):
                item = {k: self.deserializer.deserialize(v) for k, v in raw.items()}
                if item['owner'] != owner or int(item['expires_at']) <= int(self.clock()):
                    continue
                batches.append(dict(version=int(item['version']), operation=item['operation'],
                                    frames=json.loads(item['frames'])))
            if not page.get('LastEvaluatedKey'):
                return batches
            args['ExclusiveStartKey'] = page['LastEvaluatedKey']
