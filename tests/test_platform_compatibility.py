"""Offline checks for Windows-safe persistence and provider budget locking."""
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from stardew_agent.core import append, read, rows, write
from verification.common import dump, jsonl, load, read_jsonl


def test_utf8_persistence(tmp_path):
    value = {'作物': '防风草 🌱'}
    document = tmp_path / '知识.json'
    ledger = tmp_path / '记录.jsonl'
    write(document, value)
    assert read(document) == value
    assert '防风草' in document.read_bytes().decode('utf-8')
    append(ledger, value)
    assert rows(ledger) == [value]
    dump(document, value)
    assert load(document) == value
    jsonl(ledger, [value])
    assert read_jsonl(ledger) == [value]


def test_process_lock_prevents_lost_updates(tmp_path):
    ledger = tmp_path / 'budget.json'
    write(ledger, {'calls': 0})
    worker = """
import sys
from pathlib import Path
from filelock import FileLock
from stardew_agent.core import read, write
p = Path(sys.argv[1])
for _ in range(20):
    with FileLock(p.with_suffix('.lock')):
        state = read(p)
        write(p, {'calls': state['calls'] + 1})
"""
    processes = [subprocess.Popen([sys.executable, '-c', worker, str(ledger)]) for _ in range(3)]
    try:
        assert all(process.wait(timeout=30) == 0 for process in processes)
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait()
    assert read(ledger)['calls'] == 60


def test_provider_budget_is_bounded_without_network(tmp_path, monkeypatch):
    import verification.chatecnu as provider

    monkeypatch.setattr(provider, 'BASE', tmp_path)
    monkeypatch.setattr(provider, 'dotenv_values', lambda _: {
        'CHATECNU_BASE_URL': 'https://chat.ecnu.edu.cn/open/api/v1',
        'CHATECNU_API_KEY': 'synthetic-test-key',
        'CHATECNU_MAX_CALLS': '3',
    })

    class OfflineClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, *args, **kwargs):
            raise provider.httpx.ConnectError('Offline test')

    monkeypatch.setattr(provider.httpx, 'Client', OfflineClient)
    client = provider.ChatECNU()
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: client.call('test', [], label='offline'), range(8)))
    assert sum(row.get('reason') == 'CALL_LIMIT' for row in results) == 5
    assert read(tmp_path / 'logs/api_budget.json')['calls'] == 3


def test_workbench_serves_frontend_without_snapshot(tmp_path, monkeypatch):
    import threading
    import httpx
    import stardew_agent.knowledge as knowledge
    import stardew_agent.server as server
    from stardew_agent.state import TaskStore

    monkeypatch.setattr(knowledge, 'DATA', tmp_path)
    monkeypatch.setattr(server, 'TaskStore', lambda: TaskStore(tmp_path / 'tasks.sqlite3'))
    frontend = tmp_path / 'frontend'
    frontend.mkdir()
    (frontend / 'index.html').write_text('<div id="root">鹈鹕镇助手</div>', encoding='utf-8')
    monkeypatch.setattr(server, 'FRONTEND_DIST', frontend)
    app = server.make_server(port=0)
    worker = threading.Thread(target=app.serve_forever, daemon=True)
    worker.start()
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{app.server_port}', trust_env=False) as client:
            page = client.get('/')
            assert page.status_code == 200 and 'id="root"' in page.text
            result = client.get('/api/bootstrap')
            assert result.status_code == 200
            boot = result.json()
            assert boot['snapshot'] is None and boot['knowledge_status'] == 'MISSING'
            assert boot['csrf'] and 'CHATECNU_API_KEY' not in result.text
            assert client.get('/api/evaluations').status_code == 200
            headers = {'Origin': str(client.base_url).rstrip('/'), 'X-CSRF-Token': boot['csrf']}
            result = client.post('/api/task', json={}, headers=headers)
            assert result.status_code == 400 and result.json()['error'] == 'NO_RELEASED_SNAPSHOT'
            assert client.post('/api/task', json={}).status_code == 403
            for route in ('/api/search?q=土豆', '/api/review', '/api/graph'):
                result = client.get(route)
                assert result.status_code == 400 and result.json()['error'] == 'NO_RELEASED_SNAPSHOT'
    finally:
        app.shutdown()
        app.server_close()
        worker.join(timeout=5)


def test_bootstrap_preserves_available_snapshot(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import stardew_agent.server as server
    from stardew_agent.state import TaskStore

    monkeypatch.setattr(server, 'TaskStore', lambda: TaskStore(tmp_path / 'tasks.sqlite3'))
    app = server.Workbench()
    manifest = {'snapshot_id': 'a' * 64, 'counts': {'entities': 1}}
    monkeypatch.setattr(app, 'snapshot', lambda: SimpleNamespace(manifest=manifest))
    boot = app.get('/api/bootstrap', {})
    assert boot['snapshot'] == manifest and boot['knowledge_status'] == 'AVAILABLE'
    assert boot['csrf'] == app.token


def test_bootstrap_does_not_hide_corrupted_knowledge(tmp_path, monkeypatch):
    import pytest
    import stardew_agent.server as server
    from stardew_agent.core import ValidationError
    from stardew_agent.state import TaskStore

    monkeypatch.setattr(server, 'TaskStore', lambda: TaskStore(tmp_path / 'tasks.sqlite3'))
    app = server.Workbench()

    def corrupted():
        raise ValidationError('SNAPSHOT_FILE_CHANGED:graph.json')

    monkeypatch.setattr(app, 'snapshot', corrupted)
    with pytest.raises(ValidationError, match='SNAPSHOT_FILE_CHANGED'):
        app.get('/api/bootstrap', {})
