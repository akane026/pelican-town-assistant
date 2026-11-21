"""Browser credentials are request-scoped and must not reach persistent state."""
import json
import threading

import httpx
import pytest

import stardew_agent.server as server
from stardew_agent.core import ValidationError
from stardew_agent.state import TaskStore


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'ROOT', tmp_path)
    monkeypatch.setattr(server, 'ARTIFACTS', tmp_path / 'artifacts')
    monkeypatch.setattr(server, 'TaskStore', lambda: TaskStore(tmp_path / 'tasks.sqlite3'))
    (tmp_path / '.env').write_text(
        'CHATECNU_BASE_URL=https://chat.ecnu.edu.cn/open/api/v1\n'
        'CHATECNU_MODEL=ecnu-max\nCHATECNU_VISION_MODEL=ecnu-plus\n'
        'CHATECNU_API_KEY=synthetic-disk-key\nCHATECNU_MAX_CALLS=0\n', encoding='utf-8')
    return tmp_path


@pytest.mark.parametrize('key', [None, '', 'has spaces', 'has\nnewline', '非ASCII', 'x' * 513])
def test_invalid_or_missing_key_never_falls_back_to_env(isolated, key):
    with pytest.raises(ValidationError, match='API_KEY'):
        server.browser_model_client(key)


def test_browser_key_overrides_disk_without_changing_budget_or_env(isolated):
    path = isolated / '.env'
    before = path.read_bytes()
    client = server.browser_model_client('synthetic-browser-key')
    assert client.client.key == 'synthetic-browser-key'
    assert client.client.limit == 0
    assert path.read_bytes() == before


def test_concurrent_turns_do_not_share_or_persist_credentials(isolated, monkeypatch):
    barrier = threading.Barrier(2)
    seen = {}
    providers = []

    class FakeAgent:
        def __init__(self, tasks, client):
            self.client = client

        def run(self, task_id, message):
            barrier.wait(timeout=5)
            seen[task_id] = self.client.client.key
            providers.append(self.client.client)

    monkeypatch.setattr(server, 'Agent', FakeAgent)
    app = server.Workbench()
    task_ids = [app.tasks.create('synthetic-snapshot')['task_id'] for _ in range(2)]
    keys = ['synthetic-browser-one', 'synthetic-browser-two']
    for task_id, key in zip(task_ids, keys):
        app.chat(task_id, '土豆多少钱？', api_key=key)
    for job in app.jobs.values():
        job.join(timeout=10)
        assert not job.is_alive()
    assert seen == dict(zip(task_ids, keys))
    assert all(not p.key and 'CHATECNU_API_KEY' not in p.config for p in providers)
    for key in keys:
        assert key not in json.dumps(app.tasks.list())
        assert key.encode() not in (isolated / 'tasks.sqlite3').read_bytes()
        assert key not in (isolated / '.env').read_text()


def test_http_auth_and_error_logs_do_not_expose_key(isolated, monkeypatch):
    class FailingAgent:
        def __init__(self, tasks, client):
            self.client = client

        def run(self, task_id, message):
            raise RuntimeError('synthetic failure ' + self.client.client.key)

    monkeypatch.setattr(server, 'Agent', FailingAgent)
    http_server = server.make_server(port=0)
    app = http_server.app
    task_id = app.tasks.create('synthetic-snapshot')['task_id']
    thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{http_server.server_port}'
    key = 'synthetic-header-key'
    try:
        with httpx.Client(base_url=url, trust_env=False) as client:
            headers = {'Origin': url, 'X-CSRF-Token': app.token}
            body = {'task_id': task_id, 'message': '土豆多少钱？'}
            assert client.post('/api/chat', headers=headers, json=body).json()['error'] == 'API_KEY_REQUIRED'
            auth = {**headers, 'Authorization': 'Bearer ' + key}
            denied = client.post('/api/chat', headers={**auth, 'Origin': 'https://attacker.example'}, json=body)
            assert denied.status_code == 403
            result = client.post('/api/chat', headers=auth, json=body)
            assert result.status_code == 200 and key not in result.text
            app.jobs[task_id].join(timeout=5)
            assert not app.jobs[task_id].is_alive()
            errors = (isolated / 'artifacts/server_errors' / (task_id + '.json')).read_text()
            assert key not in errors and '[REDACTED]' in errors
            assert key not in json.dumps(app.tasks.get(task_id))
    finally:
        http_server.shutdown()
        http_server.server_close()
        thread.join(timeout=5)
