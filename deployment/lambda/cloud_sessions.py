"""DynamoDB session adapter. No clients/resources are created on import.

Stage 2: call only from trusted backend code after authenticating the user.
This is not an HTTP handler; never accept an unverified owner from a browser.
"""
import hashlib
import json
import re
import time
from decimal import Decimal
from boto3.dynamodb.types import TypeSerializer, TypeDeserializer
from botocore.exceptions import ClientError
from session_core import Session, NewSession, Capture
from serverless_state import checkpoint, restore, process_batch
from serialization import json_scalar
import lstm_analysis


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
        # DynamoDB reads numeric metadata as Decimal; our flat records use integers.
        item={k:(int(v) if isinstance(v,Decimal) and v==v.to_integral_value() else v)
              for k,v in item.items()}
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
        response = dict(session_id=sid, version=0, **session.response(), lstm=lstm_analysis.public_state(None))
        item = dict(pk='SESSION#'+sid, sk='STATE', owner=owner, version=0,
                    created_at=int(self.clock()), input_source=session.input_source,
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
            self.status(owner, sid)  # Register legacy/replayed sessions in the owner catalog.
            return json.loads(existing['create_response'])
        self._ensure_catalog(item, response)
        return response

    def status(self, owner, sid):
        item = self._session(owner, sid)
        session, _ = restore(item['checkpoint'])
        response = dict(session_id=sid, version=int(item['version']),
                    dimensions={'width':session.width,'height':session.height},
                    input_source=session.input_source, **session.response())
        response['lstm'] = lstm_analysis.public_state(json.loads(item['lstm_state']) if item.get('lstm_state') else None)
        self._ensure_catalog(item, response)
        return response

    def _catalog(self, item, response):
        sid=item['pk'].removeprefix('SESSION#')
        # Legacy session start is estimated from its original retention deadline.
        created=int(item.get('created_at',int(item['expires_at'])-self.retention))
        return dict(pk='OWNER#'+item['owner'],sk=f'SESSION#{created:013d}#{sid}',
                    owner=item['owner'],session_id=sid,version=int(response['version']),
                    created_at=created,created_at_estimated='created_at' not in item,
                    expires_at=int(item['expires_at']),closed=bool(response['closed']),
                    complete=int(response['complete']),cycles=int(response['cycles']),
                    attempt_count=len(response.get('attempts',[])),
                    input_source=response.get('input_source',item.get('input_source','unspecified')))

    def _ensure_catalog(self, item, response):
        row=self._catalog(item,response)
        found=self.client.get_item(TableName=self.table,ConsistentRead=True,
            Key=self._encode({'pk':row['pk'],'sk':row['sk']})).get('Item')
        if found and int(self.deserializer.deserialize(found['version']))>=row['version']:
            return
        try:
            self.client.put_item(TableName=self.table,Item=self._encode(row),
                ConditionExpression='attribute_not_exists(#v) OR #v <= :v',
                ExpressionAttributeNames={'#v':'version'},
                ExpressionAttributeValues=self._encode({':v':row['version']}))
        except ClientError as exc:
            if exc.response['Error']['Code']!='ConditionalCheckFailedException':raise

    def list_sessions(self, owner, body):
        _owner(owner)
        if not isinstance(body,dict) or set(body)-{'before','limit'}:
            raise ValueError('Invalid session-list fields')
        limit=body.get('limit',10);before=body.get('before')
        if type(limit) is not int or not 1<=limit<=20:
            raise ValueError('Limit must be 1..20')
        if before is not None and (not isinstance(before,str) or not re.fullmatch(r'SESSION#[0-9]{13}#[A-Za-z0-9_-]{1,64}',before)):
            raise ValueError('Invalid session-list cursor')
        args=dict(TableName=self.table,ConsistentRead=True,ScanIndexForward=False,Limit=limit,
            KeyConditionExpression='pk = :pk AND begins_with(sk, :prefix)',
            FilterExpression='expires_at > :now',ExpressionAttributeValues=self._encode({
                ':pk':'OWNER#'+owner,':prefix':'SESSION#',':now':int(self.clock())}))
        if before:args['ExclusiveStartKey']=self._encode({'pk':'OWNER#'+owner,'sk':before})
        page=self.client.query(**args);items=[]
        for raw in page.get('Items',[]):
            row={k:self.deserializer.deserialize(v) for k,v in raw.items()}
            if row['owner']!=owner:continue
            items.append({k:(int(v) if k in ('version','created_at','expires_at','complete','cycles','attempt_count') else v)
                          for k,v in row.items() if k not in ('pk','sk','owner')})
        key=page.get('LastEvaluatedKey')
        return dict(items=items,next_before=self.deserializer.deserialize(key['sk']) if key else None)

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
        auxiliary = json.loads(item['lstm_state']) if item.get('lstm_state') else None
        if operation == 'frames':
            batch = process_batch(item['checkpoint'], body)
            serialized, rows = batch['checkpoint'], batch['frames']
            result = batch['responses'][-1]
            auxiliary = lstm_analysis.analyze(auxiliary, rows, session.width, session.height)
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
        response = dict(session_id=sid, version=version, **result, lstm=lstm_analysis.public_state(auxiliary))
        updated = dict(item, checkpoint=serialized, version=version,
                       expires_at=int(item['expires_at']))
        if auxiliary is not None:
            updated['lstm_state'] = _json(auxiliary)
        elif 'lstm_state' in updated:
            del updated['lstm_state']
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
        catalog=self._catalog(updated,dict(response,input_source=session.input_source))
        writes.append(dict(Put=dict(TableName=self.table,Item=self._encode(catalog),
            ConditionExpression='attribute_not_exists(#v) OR #v <= :new',
            ExpressionAttributeNames={'#v':'version'},
            ExpressionAttributeValues=self._encode({':new':version}))))
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

    def history_page(self, owner, sid, body):
        """Bounded export with a stable version ceiling and numeric cursor."""
        return self._history_page(owner, sid, body, 3, False)

    def angles_page(self, owner, sid, body):
        """Read one DynamoDB page; return chart fields only, including old sessions.

        The 1 MiB DynamoDB query cap still applies before projection. No cache
        writes, new indexes or landmark transfers to the browser are needed.
        """
        return self._history_page(owner, sid, body, 100, True)

    def export_page(self, owner, sid, body):
        """Full frames, bounded by one query and a 900 KiB JSON response budget."""
        return self._history_page(owner, sid, body, 100, False, 900*1024)

    def _history_page(self, owner, sid, body, max_limit, compact, byte_budget=None):
        if not isinstance(body, dict) or set(body)-{'after_version','through_version','limit'}:
            raise ValueError('Invalid history pagination fields')
        item = self._session(owner, sid)
        after = body.get('after_version', 0)
        through = body.get('through_version', int(item['version']))
        limit = body.get('limit', max_limit)
        if (type(after) is not int or type(through) is not int or type(limit) is not int
                or after < 0 or through < after or through > int(item['version'])
                or not 1 <= limit <= max_limit):
            raise ValueError('Invalid history page bounds')
        if through == after:
            return dict(session_id=sid,batches=[],through_version=through,next_after_version=None)
        page = self.client.query(TableName=self.table, ConsistentRead=True, Limit=limit,
            KeyConditionExpression='pk = :pk AND sk BETWEEN :lo AND :hi',
            ExpressionAttributeValues=self._encode({':pk':'SESSION#'+sid,
                ':lo':f'HISTORY#{after+1:010d}',':hi':f'HISTORY#{through:010d}'}))
        batches=[]
        used_bytes=1024  # Reserve space for response metadata and separators.
        truncated=False
        for raw in page.get('Items',[]):
            row={k:self.deserializer.deserialize(v) for k,v in raw.items()}
            if row['owner'] != owner or int(row['expires_at']) <= int(self.clock()):
                raise Expired('History expired')
            frames = json.loads(row['frames'])
            if compact:
                frames = [dict(t=f.get('t'), mode=f.get('mode'), phase=f.get('phase'),
                    quality=dict(accepted=(f.get('quality') or {}).get('accepted')),
                    lstm=({k:v for k,v in f['lstm'].items() if k != 'outputs'}
                        if isinstance(f.get('lstm'),dict) else None),
                    measurement=({k:f['measurement'].get(k) for k in ('knee','hip','lean')}
                        if isinstance(f.get('measurement'),dict) else None)) for f in frames]
            batch=dict(version=int(row['version']),operation=row['operation'],frames=frames)
            if byte_budget is not None:
                size=len(json.dumps(batch,allow_nan=False,separators=(',', ':'),default=json_scalar).encode('utf-8'))+1
                if used_bytes+size > byte_budget:
                    if not batches:
                        raise ValueError('One history record exceeds export response budget')
                    truncated=True
                    break
                used_bytes+=size
            batches.append(batch)
        cursor = batches[-1]['version'] if batches and (truncated or page.get('LastEvaluatedKey')) else None
        return dict(session_id=sid,batches=batches,through_version=through,next_after_version=cursor)

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
