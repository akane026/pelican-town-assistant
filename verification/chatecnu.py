"""Compatibility entry point for historical verification probes."""
from __future__ import annotations

import json

import httpx
from dotenv import dotenv_values

from stardew_agent.providers import ChatECNU as RuntimeChatECNU
from .common import ROOT, BASE, dump


class ChatECNU(RuntimeChatECNU):
    """Keep probe logs isolated from the production runtime."""

    def __init__(self):
        super().__init__(config=dotenv_values(ROOT / '.env'), logbase=BASE)


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
