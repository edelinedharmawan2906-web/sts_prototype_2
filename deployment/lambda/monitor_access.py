"""Read-only, exact-session IoT access, issued after session ownership checks.

Only a short-lived signed WebSocket URL leaves Lambda, never the secret key.
Do not log URLs or STS responses. No credentials cached between callers.
"""
from datetime import datetime, timezone
from functools import lru_cache
import json
import os
import re
from urllib.parse import quote
from uuid import uuid4

import boto3
from botocore.auth import SigV4QueryAuth
from botocore.awsrequest import AWSRequest
from botocore.config import Config
from botocore.credentials import Credentials
from iot_publish import _endpoint, snapshot

ROLE_ARN = 'arn:aws:iam::871993977950:role/sts-monitor-role'
IOT_ARN = 'arn:aws:iot:ap-southeast-2:871993977950:'


@lru_cache(maxsize=1)
def _sts():
    return boto3.client('sts', region_name='ap-southeast-2',
        config=Config(connect_timeout=2, read_timeout=3,
            retries={'mode':'standard','total_max_attempts':1}))


def scoped_policy(topic, client_id):
    return {'Version':'2012-10-17','Statement':[
        {'Effect':'Allow','Action':'iot:Connect','Resource':IOT_ARN+'client/'+client_id},
        {'Effect':'Allow','Action':'iot:Subscribe','Resource':IOT_ARN+'topicfilter/'+topic},
        {'Effect':'Allow','Action':'iot:Receive','Resource':IOT_ARN+'topic/'+topic}]}


def issue_connection(owner, sid):
    if os.getenv('STS_IOT_ENABLED','0') != '1':
        raise ValueError('Enable STS_IOT_ENABLED before using the monitor')
    endpoint = _endpoint()
    role = os.getenv('STS_MONITOR_ROLE_ARN','').strip()
    if role != ROLE_ARN:
        raise ValueError('Set STS_MONITOR_ROLE_ARN to sts-monitor-role ARN')
    if (not isinstance(owner,str)
            or not re.fullmatch(r'(?:cognito-[0-9a-f]{64}|console-test)',owner)
            or not isinstance(sid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',sid)):
        raise ValueError('Invalid monitor scope')
    client_id = 'sts-monitor-'+uuid4().hex
    topic = f'sts/cloud/{owner}/{sid}/state'
    assumed = _sts().assume_role(RoleArn=role, RoleSessionName=client_id,
        DurationSeconds=900,
        Policy=json.dumps(scoped_policy(topic,client_id),separators=(',',':')))
    creds = assumed['Credentials']
    now = datetime.now(timezone.utc)
    expiration = creds['Expiration']
    if expiration.tzinfo is None or (expiration-now).total_seconds()<120:
        raise RuntimeError('Temporary credentials expire too soon')
    # AWS IoT Core specifically requires appending the session token AFTER
    # calculating the signature; it is omitted from the canonical query.
    request = AWSRequest(method='GET',url='https://'+endpoint+'/mqtt')
    signing_creds = Credentials(creds['AccessKeyId'],creds['SecretAccessKey'])
    SigV4QueryAuth(signing_creds,'iotdevicegateway','ap-southeast-2',expires=60).add_auth(request)
    signed_url = request.url.replace('https://','wss://',1)
    signed_url += '&X-Amz-Security-Token='+quote(creds['SessionToken'],safe='')
    return dict(url=signed_url,client_id=client_id,topic=topic,
        connect_within_seconds=60,credentials_expire_at=expiration.isoformat(),
        qos=1,read_only=True)


def monitor_connection(store, owner, sid):
    # status validates owner AND TTL before any access can be issued.
    state = store.status(owner,sid)
    result = issue_connection(owner,sid)
    _,initial = snapshot(owner,'status',state)
    result['initial_state'] = initial
    return dict(status='ok',result=result)


def monitor_test():
    result = issue_connection('console-test','monitor-access-test')
    # Console test confirms STS and URL generation only, not broker acceptance.
    return dict(status='ok',monitor=dict(assume_role=True,url_generated=True,
        read_only=True,scope='single_test_session',
        credentials_duration_seconds=900,connect_within_seconds=60),
        note='Temporary-access test only; no broker connection or DynamoDB write')
