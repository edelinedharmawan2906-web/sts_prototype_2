"""Best-effort IoT snapshots after a successful DynamoDB commit.

No clients on import. No browser-supplied topic/endpoint. Consumers must dedupe
(event_id) and ignore lower versions. This is not a durable delivery outbox.
"""
from functools import lru_cache
import hashlib
import json
import logging
import os
import re
import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)


def _endpoint():
    endpoint=os.getenv('STS_IOT_ENDPOINT','').strip()
    if not re.fullmatch(r'[a-z0-9]+-ats\.iot\.ap-southeast-2\.amazonaws\.com',endpoint):
        raise ValueError('STS_IOT_ENDPOINT must be a Sydney ATS host without https://')
    return endpoint


@lru_cache(maxsize=2)
def _client(endpoint):
    return boto3.client('iot-data',region_name='ap-southeast-2',endpoint_url='https://'+endpoint,
        config=Config(connect_timeout=1,read_timeout=2,
            retries={'mode':'standard','total_max_attempts':1}))


def _send(topic,payload):
    raw=json.dumps(payload,allow_nan=False,separators=(',',':')).encode()
    if len(raw)>16*1024:
        raise ValueError('Snapshot exceeds learning payload budget')
    _client(_endpoint()).publish(topic=topic,qos=1,retain=False,payload=raw)


def snapshot(owner,operation,state,t=None):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',owner):raise ValueError('Invalid owner')
    sid=state['session_id'];version=state['version']
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',sid) or type(version) is not int or version<0:
        raise ValueError('Invalid committed session version')
    topic=f'sts/cloud/{owner}/{sid}/state'
    attempts=state.get('attempts',[])
    payload=dict(schema='sts-live-v1',event_id=hashlib.sha256(f'{owner}|{sid}|{version}'.encode()).hexdigest(),
        session_id=sid,version=version,operation=operation,t=t,
        mode=state.get('mode'),phase=state.get('phase'),message=state.get('message'),
        complete=state['complete'],cycles=state['cycles'],closed=state['closed'],
        attempt_count=len(attempts)+(1 if state.get('phase')=='BANGKIT' else 0),
        quality=state.get('quality'),measurement=state.get('measurement'),
        lstm=({k:v for k,v in state['lstm'].items() if k != 'outputs'}
              if isinstance(state.get('lstm'),dict) else None))
    return topic,payload


def publish_committed(owner,operation,state,t=None):
    if os.getenv('STS_IOT_ENABLED','0')!='1':return dict(enabled=False,published=False)
    try:
        topic,payload=snapshot(owner,operation,state,t)
        _send(topic,payload)
        return dict(enabled=True,published=True,topic=topic,event_id=payload['event_id'],version=state['version'])
    except Exception as exc:
        # Never undo a committed frame batch or trigger a second analysis write.
        code=getattr(exc,'response',{}).get('Error',{}).get('Code',type(exc).__name__)
        logger.warning('STS IoT publish failed: %s',code)
        return dict(enabled=True,published=False,code=code)


def publish_test(request_id):
    if os.getenv('STS_IOT_ENABLED','0')!='1':
        return dict(status='error',code='IOT_DISABLED',message='Set STS_IOT_ENABLED=1')
    topic='sts/cloud/test/lambda'
    payload=dict(schema='sts-mqtt-test-v1',event_id=request_id,message='Tes Lambda ke AWS IoT Core',
        complete=1,cycles=1,synthetic=True)
    try:
        _send(topic,payload)
        return dict(status='ok',mqtt=dict(published=True,topic=topic,event_id=request_id),
                    note='Synthetic publish test; no camera session created')
    except Exception as exc:
        code=getattr(exc,'response',{}).get('Error',{}).get('Code',type(exc).__name__)
        logger.warning('STS IoT test failed: %s',code)
        return dict(status='error',code=code,message='Check endpoint, iot:Publish permission and network')
