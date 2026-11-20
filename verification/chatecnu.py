"""Bounded ChatECNU adapter. Never logs credentials, headers or reasoning content."""
from __future__ import annotations
import base64
import fcntl
import json
import time
import uuid
from pathlib import Path
import httpx
from dotenv import dotenv_values
from .common import ROOT, BASE, dump, now, sha


class ChatECNU:
    def __init__(self):
        self.config = dotenv_values(ROOT / '.env')
        self.key = self.config.get('CHATECNU_API_KEY') or ''
        self.url = (self.config.get('CHATECNU_BASE_URL') or '').rstrip('/')
        if self.url != 'https://chat.ecnu.edu.cn/open/api/v1':
            raise ValueError('Unexpected API host; explicit configuration required')
        self.limit = int(self.config.get('CHATECNU_MAX_CALLS') or 0)

    def call(self, model, messages, *, label, **options):
        if not self.key:
            return {'label': label, 'status': 'BLOCKED', 'reason': 'API_KEY_MISSING'}
        ledger = BASE / 'logs' / 'api_budget.json'
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.with_suffix('.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            state = json.loads(ledger.read_text()) if ledger.exists() else {'calls': 0}
            if state['calls'] >= self.limit:
                return {'label': label, 'status': 'BLOCKED', 'reason': 'CALL_LIMIT'}
            state['calls'] += 1
            dump(ledger, state)
        request = {'model': model, 'messages': messages, 'stream': False,
                   'max_tokens': int(self.config.get('CHATECNU_MAX_OUTPUT_TOKENS') or 1024), **options}
        result = {'label': label, 'model_requested': model, 'at': now(), 'call_number': state['calls'],
                  'fixture': False, 'request_sha256': sha(json.dumps(request, sort_keys=True).encode())}
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
        dump(BASE / 'logs' / 'chatecnu' / (str(uuid.uuid4()) + '.json'), result)
        return result

    def image_content(self, path):
        path = Path(path)
        mime = 'image/png' if path.suffix == '.png' else 'image/webp' if path.suffix == '.webp' else 'image/jpeg'
        return {'type': 'image_url', 'image_url': {'url': 'data:' + mime + ';base64,' + base64.b64encode(path.read_bytes()).decode()}}


def probe():
    api = ChatECNU(); rows = []
    for model in [api.config['CHATECNU_MODEL'], api.config['CHATECNU_VISION_MODEL']]:
        tasks = [
            ('text', [{'role': 'user', 'content': '连通性测试。只回答：测试成功'}], {}),
            ('json', [{'role': 'user', 'content': '输出 JSON 对象，字段 ok 为 true，sum 为 7。不要解释。'}],
             {'response_format': {'type': 'json_object'}}),
            ('tool', [{'role': 'user', 'content': '请调用 add 工具计算 3 加 4。'}],
             {'tools': [{'type': 'function', 'function': {'name': 'add', 'description': 'Add integers',
               'parameters': {'type': 'object', 'properties': {'a': {'type': 'integer'}, 'b': {'type': 'integer'}},
                              'required': ['a', 'b'], 'additionalProperties': False}}}],
              'tool_choice': {'type': 'function', 'function': {'name': 'add'}}}),
            ('vision', [{'role': 'user', 'content': [
                {'type': 'text', 'text': '这是接口视觉测试。请描述图片的画风，并说出画面中央打开的菜单类型。不要根据文件名猜测。'},
                api.image_content(BASE / 'data/external/autosaved_inventory.webp')]}], {}),
        ]
        for label, messages, options in tasks:
            r = api.call(model, messages, label=model + ':' + label, **options)
            if label == 'text': r['validated'] = r.get('status') == 'OK' and '测试成功' in (r.get('content') or '')
            elif label == 'json':
                try: r['validated'] = json.loads(r.get('content') or '') == {'ok': True, 'sum': 7}
                except ValueError: r['validated'] = False
            elif label == 'tool':
                try:
                    fn = r['tool_calls'][0]['function']; args = json.loads(fn['arguments'])
                    r['validated'] = fn['name'] == 'add' and args == {'a': 3, 'b': 4}
                except (TypeError, KeyError, ValueError, IndexError): r['validated'] = False
            else:
                r['validated'] = None
                r['review'] = 'Requires visual answer review; HTTP success does not establish recognition accuracy'
            rows.append(r)
            dump(BASE / 'results/model_probe.json', {'at': now(), 'status': 'RUNNING', 'probes': rows})
            print(r['label'], r['status'], r.get('validated'), r.get('latency_seconds'), flush=True)
            if r.get('http_status') in (401, 403, 429):
                dump(BASE / 'results/model_probe.json', {'at': now(), 'status': 'BLOCKED', 'probes': rows}); return 2
    dump(BASE / 'results/model_probe.json', {'at': now(), 'status': 'EXECUTED', 'probes': rows})
    return 0


if __name__ == '__main__':
    raise SystemExit(probe())
