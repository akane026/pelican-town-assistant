"""Runtime model transport, bounded call accounting and per-instance request logs.

Only budget reservation holds the process lock; HTTP calls may run concurrently.
An attempted HTTP call consumes a slot even on failure. No automatic retries.
"""
from __future__ import annotations

import base64
import json
import time
import uuid
from pathlib import Path
from typing import Mapping, Protocol

import httpx
from dotenv import dotenv_values
from filelock import FileLock

from .core import ARTIFACTS, ROOT, digest, now, write


class ModelProvider(Protocol):
    config: Mapping[str, str | None]

    def call(self, model, messages, *, label, **options) -> dict: ...

    def image_content(self, path) -> dict: ...


class ChatECNU:
    def __init__(self, *, config=None, logbase=None, initial_calls=0):
        self.config = dict(config if config is not None else dotenv_values(ROOT / '.env'))
        self.logbase = Path(logbase) if logbase is not None else ARTIFACTS / 'model'
        if type(initial_calls) is not int or initial_calls < 0:
            raise ValueError('initial_calls must be a nonnegative integer')
        self.initial_calls = initial_calls
        self.key = self.config.get('CHATECNU_API_KEY') or ''
        self.url = (self.config.get('CHATECNU_BASE_URL') or '').rstrip('/')
        if self.url != 'https://chat.ecnu.edu.cn/open/api/v1':
            raise ValueError('Unexpected API host; explicit configuration required')
        self.limit = int(self.config.get('CHATECNU_MAX_CALLS') or 0)
        if self.limit < 0:
            raise ValueError('CHATECNU_MAX_CALLS must be nonnegative')

    def call(self, model, messages, *, label, **options):
        if not self.key:
            return {'label': label, 'status': 'BLOCKED', 'reason': 'API_KEY_MISSING'}
        ledger = self.logbase / 'logs' / 'api_budget.json'
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(ledger.with_suffix('.lock')):
            state = json.loads(ledger.read_text(encoding='utf-8')) if ledger.exists() else {'calls': self.initial_calls, 'initial_legacy_calls': self.initial_calls}
            if state['calls'] >= self.limit:
                return {'label': label, 'status': 'BLOCKED', 'reason': 'CALL_LIMIT'}
            state['calls'] += 1
            write(ledger, state)
        request = {'model': model, 'messages': messages, 'stream': False,
                   'max_tokens': int(self.config.get('CHATECNU_MAX_OUTPUT_TOKENS') or 1024), **options}
        result = {'request_id': str(uuid.uuid4()), 'label': label, 'model_requested': model, 'at': now(), 'call_number': state['calls'],
                  'fixture': False, 'request_sha256': digest(json.dumps(request, sort_keys=True).encode())}
        start = time.monotonic()
        try:
            with httpx.Client(timeout=httpx.Timeout(90, connect=15), follow_redirects=False) as client:
                response = client.post(self.url + '/chat/completions',
                    headers={'Authorization': 'Bearer ' + self.key}, json=request)
            result['http_status'] = response.status_code
            if response.status_code != 200:
                result.update(status='API_ERROR', reason='HTTP_' + str(response.status_code))
            else:
                data = response.json(); choice = data.get('choices', [{}])[0]
                msg = choice.get('message', {})
                # Only final answer / tool arguments, never provider hidden reasoning.
                result.update(status='OK', model_returned=data.get('model'), usage=data.get('usage'),
                              finish_reason=choice.get('finish_reason'), content=msg.get('content'),
                              tool_calls=msg.get('tool_calls'))
        except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
            result.update(status='ERROR', reason=type(exc).__name__)
        result['latency_seconds'] = round(time.monotonic() - start, 3)
        # Defensive redaction even if a provider unexpectedly echoes a credential.
        result = json.loads(json.dumps(result, ensure_ascii=False).replace(self.key, '[REDACTED]'))
        write(self.logbase / 'logs' / 'chatecnu' / (result['request_id'] + '.json'), result)
        return result

    def image_content(self, path):
        path = Path(path)
        mime = 'image/png' if path.suffix == '.png' else 'image/webp' if path.suffix == '.webp' else 'image/jpeg'
        return {'type': 'image_url', 'image_url': {'url': 'data:' + mime + ';base64,' + base64.b64encode(path.read_bytes()).decode()}}

