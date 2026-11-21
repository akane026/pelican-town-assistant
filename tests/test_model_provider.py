"""Provider boundaries tested with local HTTP transports, never a live API."""
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from stardew_agent import model, providers
from stardew_agent.core import read


@pytest.fixture
def config():
    return {
        'CHATECNU_BASE_URL': 'https://chat.ecnu.edu.cn/open/api/v1',
        'CHATECNU_API_KEY': 'synthetic-secret',
        'CHATECNU_MODEL': 'text-test',
        'CHATECNU_VISION_MODEL': 'vision-test',
        'CHATECNU_MAX_CALLS': '5',
    }


def install_transport(monkeypatch, handler):
    client_class = httpx.Client
    monkeypatch.setattr(providers.httpx, 'Client', lambda **kw: client_class(
        transport=httpx.MockTransport(handler), **kw))


def test_network_is_not_serialized_and_shared_budget_is_atomic(tmp_path, config, monkeypatch):
    barrier = threading.Barrier(2)

    def respond(request):
        barrier.wait(timeout=5)
        return httpx.Response(200, json={'choices': [{'message': {'content': 'ok'}}]})

    install_transport(monkeypatch, respond)
    clients = [model.ModelClient(provider=providers.ChatECNU(
        config=config, logbase=tmp_path)) for _ in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda client: client.call([], label='parallel'), clients))
    assert all(row['status'] == 'OK' for row in results)
    assert sorted(row['call_number'] for row in results) == [1, 2]
    assert read(tmp_path / 'logs/api_budget.json')['calls'] == 2
    assert len({row['request_id'] for row in results}) == 2


def test_probe_and_runtime_logs_are_isolated(tmp_path, config, monkeypatch):
    import verification.chatecnu as probe

    probe_path = tmp_path / 'probe'
    monkeypatch.setattr(probe, 'BASE', probe_path)
    monkeypatch.setattr(probe, 'dotenv_values', lambda _: config)
    install_transport(monkeypatch, lambda request: httpx.Response(
        200, json={'choices': [{'message': {'content': 'ok'}}]}))
    legacy = probe.ChatECNU()
    runtime = providers.ChatECNU(config=config, logbase=tmp_path / 'runtime')
    legacy.call('test', [], label='probe')
    runtime.call('test', [], label='runtime')
    assert probe.BASE == probe_path
    assert read(probe_path / 'logs/api_budget.json')['calls'] == 1
    assert read(tmp_path / 'runtime/logs/api_budget.json')['calls'] == 1
    assert len(list(probe_path.glob('logs/chatecnu/*.json'))) == 1
    assert len(list((tmp_path / 'runtime').glob('logs/chatecnu/*.json'))) == 1


def test_failed_attempt_consumes_budget_without_retry(tmp_path, config, monkeypatch):
    requests = []

    def limited(request):
        requests.append(request)
        return httpx.Response(429)

    install_transport(monkeypatch, limited)
    client = providers.ChatECNU(config=config, logbase=tmp_path, initial_calls=4)
    result = client.call('test', [], label='limited')
    assert result['reason'] == 'HTTP_429'
    assert client.call('test', [], label='blocked')['reason'] == 'CALL_LIMIT'
    assert len(requests) == 1
    assert read(tmp_path / 'logs/api_budget.json')['calls'] == 5


def test_request_log_is_correlated_redacted_and_excludes_reasoning(tmp_path, config, monkeypatch):
    install_transport(monkeypatch, lambda request: httpx.Response(200, json={
        'model': 'test', 'usage': {'total_tokens': 8}, 'choices': [{'message': {
            'content': 'echo synthetic-secret', 'reasoning_content': 'private reasoning',
            'tool_calls': [{'id': 'tool-1', 'type': 'function'}]}, 'finish_reason': 'tool_calls'}]}))
    client = providers.ChatECNU(config=config, logbase=tmp_path)
    result = client.call('test', [], label='trace')
    path = tmp_path / 'logs/chatecnu' / (result['request_id'] + '.json')
    assert read(path) == result and result['usage']['total_tokens'] == 8
    text = path.read_text(encoding='utf-8')
    assert 'synthetic-secret' not in text and 'private reasoning' not in text
    assert result['content'] == 'echo [REDACTED]' and result['tool_calls']


def test_provider_injection_model_selection_and_offline_mode(config):
    class Fake:
        def __init__(self):
            self.config = config
            self.models = []

        def call(self, selected, messages, *, label, **options):
            self.models.append(selected)
            return {'status': 'OK', 'content': '{}'}

    fake = Fake()
    client = model.ModelClient(provider=fake)
    client.call([])
    client.call([], vision=True)
    assert fake.models == ['text-test', 'vision-test']
    client = model.ModelClient(offline=True, provider=fake)
    assert client.call([])['reason'] == 'OFFLINE' and len(fake.models) == 2


def test_cache_isolated_by_endpoint_and_context(tmp_path, config, monkeypatch):
    monkeypatch.setattr(model, 'DATA', tmp_path / 'data')
    monkeypatch.setattr(model, 'ARTIFACTS', tmp_path / 'artifacts')

    class Fake:
        def __init__(self, endpoint):
            self.config = {**config, 'CHATECNU_BASE_URL': endpoint}
            self.calls = 0

        def call(self, selected, messages, *, label, **options):
            self.calls += 1
            return {'status': 'OK', 'content': json.dumps({'ok': True})}

    first = Fake('https://first.test/v1')
    second = Fake('https://second.test/v1')
    a = model.ModelClient(provider=first)
    b = model.ModelClient(provider=second)
    result = a.structured('test', context={'version': 1})
    cached = a.structured('test', context={'version': 1})
    changed = a.structured('test', context={'version': 2})
    other = b.structured('test', context={'version': 1})
    assert cached['execution_mode'] == 'cache'
    assert len({result['cache_key'], changed['cache_key'], other['cache_key']}) == 3
    assert first.calls == 2 and second.calls == 1
