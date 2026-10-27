"""STS Lambda: private IAM tests and HTTP API v2 with Cognito JWT authorizer.

API Gateway validates JWT signatures/expiry BEFORE invoking this integration.
Only trust its requestContext, never claims supplied in headers or JSON body.
Keep Function URL disabled and Lambda invoke permissions scoped to this API.
"""
from functools import lru_cache
from typing import Literal
import json
import logging
import os
import re
import base64
import binascii
import hashlib
import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from cloud_sessions import DynamoSessions, Conflict, NotFound, Expired
from iot_publish import publish_committed, publish_test
from monitor_access import monitor_connection, monitor_test

logger = logging.getLogger(__name__)

ISSUER = 'https://cognito-idp.ap-southeast-2.amazonaws.com/ap-southeast-2_k2QaXXosn'
CLIENT_ID = '1o3uv31tupfo8lhn1tcl776u9f'
API_ID = 'lxjml9oo40'


class Command(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    action: Literal['health','smoke_test','create','status','calibration','frames','finish','history','sessions','angles','export_history','mqtt_test','monitor_connect','monitor_test','lstm_test']
    request_id: str | None = Field(None, pattern=r'^[A-Za-z0-9_-]{1,64}$')
    session_id: str | None = Field(None, pattern=r'^[A-Za-z0-9_-]{1,64}$')
    expected_version: int | None = Field(None, ge=0)
    payload: dict | list = Field(default_factory=dict)


@lru_cache(maxsize=1)
def _client():
    return boto3.client('dynamodb', config=BotoConfig(
        connect_timeout=3, read_timeout=5,
        retries={'mode':'standard','total_max_attempts':1}))


def _store():
    table = os.getenv('STS_TABLE_NAME', '').strip()
    if not re.fullmatch(r'[A-Za-z0-9_.-]{3,255}', table):
        raise RuntimeError('Set STS_TABLE_NAME to the DynamoDB table name')
    return DynamoSessions(_client(), table)


def _required(value, name):
    if value is None:
        raise ValueError(f'{name} is required for this action')
    return value


def dispatch(command, store, owner):
    """Keep business operations testable without creating an AWS client."""
    c = command
    if c.action == 'lstm_test':
        from lstm_analysis import self_test
        return self_test()
    if c.action == 'monitor_test':
        return monitor_test()
    if c.action == 'monitor_connect':
        if c.payload != {}:
            raise ValueError('monitor_connect does not accept scope overrides')
        return monitor_connection(store,owner,_required(c.session_id,'session_id'))
    if c.action == 'mqtt_test':
        return publish_test(_required(c.request_id,'request_id'))
    if c.action == 'health':
        return dict(status='ok', mode='private_console_test',
                    table=store.table, database_checked=False)
    if c.action == 'smoke_test':
        request_id = _required(c.request_id, 'request_id')
        created = store.create(owner, {'input_source':'simulation'}, request_id)
        sid = created['session_id']
        # Fixed derived IDs plus identical content make a lost-response retry safe.
        # Each smoke ID creates a test-only session, never touches another session.
        frame_id = 'frames-'+request_id[:56]
        finish_id = 'finish-'+request_id[:56]
        store.apply(owner, sid, frame_id, 0, 'frames', [dict(t=0), dict(t=.05)])
        finished = store.apply(owner, sid, finish_id, 1, 'finish', {})
        current = store.status(owner, sid)
        batches = store.history(owner, sid)
        frame_count = sum(len(b['frames']) for b in batches)
        if current['version'] != 2 or frame_count != 2 or not current['closed']:
            raise RuntimeError('Unexpected smoke-test database state')
        return dict(status='ok', database_checked=True, table=store.table,
                    session_id=sid, version=finished['version'],
                    stored_frames=frame_count, closed=True,
                    complete=current['complete'], cycles=current['cycles'],
                    note='Synthetic storage test, not a movement assessment')
    if c.action == 'sessions':
        return dict(status='ok',result=store.list_sessions(owner,c.payload))
    if c.action == 'create':
        result = store.create(owner, c.payload, _required(c.request_id,'request_id'))
    else:
        sid = _required(c.session_id,'session_id')
        if c.action == 'status':
            result = store.status(owner, sid)
        elif c.action == 'history':
            result = store.history_page(owner, sid, c.payload)
        elif c.action == 'angles':
            result = store.angles_page(owner, sid, c.payload)
        elif c.action == 'export_history':
            result = store.export_page(owner, sid, c.payload)
        else:
            result = store.apply(owner, sid, _required(c.request_id,'request_id'),
                _required(c.expected_version,'expected_version'), c.action, c.payload)
    reply=dict(status='ok', result=result)
    if c.action in ('create','frames','calibration','finish'):
        t=c.payload[-1].get('t') if c.action=='frames' and c.payload else None
        reply['mqtt']=publish_committed(owner,c.action,result,t)
    return reply


def _private_handler(event, context):
    """Private console events only. Structured errors do not expose raw payloads."""
    try:
        if type(event) is not dict:
            raise ValueError('Event must be a JSON object')
        if any(k in event for k in ('requestContext','httpMethod','headers','rawPath')):
            return dict(status='error', code='HTTP_NOT_ENABLED',
                        message='Use private Lambda Test; HTTP authentication is not configured')
        if len(json.dumps(event, allow_nan=False).encode()) > 256*1024:
            raise ValueError('Event exceeds 256 KiB learning limit')
        command = Command.model_validate(event)
        if command.action == 'monitor_connect':
            return dict(status='error',code='FORBIDDEN',
                message='Monitor access requires authenticated HTTP')
        owner = os.getenv('STS_CONSOLE_TEST_OWNER','console-test')
        store = _store()
        result = dispatch(command, store, owner)
        if len(json.dumps(result, allow_nan=False).encode()) > 5*1024*1024:
            raise ValueError('History response too large; pagination/export is needed')
        return result
    except ValidationError:
        return dict(status='error', code='INVALID_INPUT', message='Check action, fields and value types')
    except NotFound:
        return dict(status='error', code='NOT_FOUND', message='Session not found')
    except Expired:
        return dict(status='error', code='EXPIRED', message='Session expired; create a new session')
    except Conflict as exc:
        return dict(status='error', code='CONFLICT', message=str(exc))
    except HTTPException as exc:
        return dict(status='error', code='SESSION_ERROR', message=str(exc.detail))
    except ValueError as exc:
        return dict(status='error', code='INVALID_INPUT', message=str(exc))
    except ClientError as exc:
        code = exc.response.get('Error',{}).get('Code','AWS_ERROR')
        logger.error('DynamoDB operation failed: %s', code)
        return dict(status='error', code=code,
                    message='Check table region, STS_TABLE_NAME and execution-role permissions')
    except Exception:
        logger.exception('STS private handler failed')
        return dict(status='error', code='INTERNAL_ERROR',
                    message='Check Lambda CloudWatch logs and deployment configuration')


class AuthError(Exception):
    pass


def _verified_owner(event):
    """Authorization is supplied by API Gateway, not decoded from a browser JWT."""
    rc = event.get('requestContext')
    if not isinstance(rc, dict) or event.get('version') != '2.0':
        raise AuthError()
    if rc.get('apiId') != API_ID:
        raise AuthError()
    jwt = rc.get('authorizer', {}).get('jwt', {})
    claims = jwt.get('claims', {})
    sub = claims.get('sub')
    if (claims.get('iss') != ISSUER or claims.get('client_id') != CLIENT_ID
            or claims.get('token_use') != 'access'
            or not isinstance(sub, str)
            or not re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', sub)):
        raise AuthError()
    scopes = claims.get('scope', '')
    if not isinstance(scopes, str) or 'openid' not in scopes.split():
        raise AuthError()
    return 'cognito-' + hashlib.sha256((ISSUER+'|'+sub).encode()).hexdigest()


def _http_response(status, value):
    return dict(statusCode=status, isBase64Encoded=False,
                headers={'Content-Type':'application/json', 'Cache-Control':'no-store'},
                body=json.dumps(value, allow_nan=False, separators=(',', ':')))


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON keys are not allowed')
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError('Non-finite JSON numbers are not allowed')


def _http_handler(event):
    try:
        owner = _verified_owner(event)
    except (AuthError, TypeError, AttributeError):
        return _http_response(401, dict(status='error', code='UNAUTHORIZED',
                                      message='Valid Cognito access token required'))
    rc = event['requestContext']
    http = rc.get('http')
    if (event.get('routeKey') != 'POST /sts' or not isinstance(http, dict)
            or http.get('method') != 'POST'):
        return _http_response(404, dict(status='error', code='NOT_FOUND'))
    try:
        raw = event.get('body')
        if not isinstance(raw, str) or len(raw.encode()) > 350*1024:
            raise ValueError('JSON body required; maximum decoded size is 256 KiB')
        encoded = event.get('isBase64Encoded', False)
        if type(encoded) is not bool:
            raise ValueError('Invalid body encoding')
        if encoded:
            raw = base64.b64decode(raw, validate=True).decode('utf-8')
        if len(raw.encode()) > 256*1024:
            raise ValueError('JSON body exceeds 256 KiB')
        data = json.loads(raw, object_pairs_hook=_unique_pairs, parse_constant=_invalid_constant)
        json.dumps(data, allow_nan=False)
        command = Command.model_validate(data)
        if command.action in ('smoke_test','mqtt_test','monitor_test','lstm_test'):
            return _http_response(403, dict(status='error', code='FORBIDDEN',
                                          message='Test actions are private-console only'))
        result = dispatch(command, _store(), owner)
        if command.action == 'health':
            result['mode'] = 'authenticated_http'
        if len(json.dumps(result, allow_nan=False).encode()) > 5*1024*1024:
            raise ValueError('History response too large; export/pagination needed')
        return _http_response(200, result)
    except ValidationError:
        return _http_response(400, dict(status='error', code='INVALID_INPUT',
                                      message='Check action, fields and value types'))
    except NotFound:
        return _http_response(404, dict(status='error', code='NOT_FOUND'))
    except Expired:
        return _http_response(410, dict(status='error', code='EXPIRED'))
    except Conflict:
        return _http_response(409, dict(status='error', code='CONFLICT',
                                      message='Reload session status; retry with current version'))
    except HTTPException as exc:
        return _http_response(400, dict(status='error', code='SESSION_ERROR', message=str(exc.detail)))
    except (ValueError, UnicodeError, binascii.Error, RecursionError):
        return _http_response(400, dict(status='error', code='INVALID_INPUT', message='Invalid JSON request'))
    except Exception:
        logger.exception('Authenticated STS operation failed')
        return _http_response(500, dict(status='error', code='INTERNAL_ERROR',
                                      message='Check Lambda CloudWatch logs'))


def lambda_handler(event, context):
    if isinstance(event, dict) and any(k in event for k in ('requestContext','httpMethod','headers','rawPath')):
        return _http_handler(event)
    return _private_handler(event, context)
