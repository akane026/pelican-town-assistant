import base64
import threading

import httpx
import pytest

import stardew_agent.library as library
import stardew_agent.server as server
from stardew_agent.core import ValidationError
from stardew_agent.state import TaskStore


def upload(content='土豆种植笔记', filename='potato.md', **kwargs):
    return {'kind': 'file', 'filename': filename,
            'data': base64.b64encode(content.encode()).decode(), **kwargs}


def test_crud_search_persistence_and_conflicts(tmp_path):
    path = tmp_path / 'library.sqlite3'
    store = library.LibraryStore(path)
    source = store.create(upload(title='春季笔记'))
    reopened = library.LibraryStore(path)
    assert reopened.get(source['id'])['content'] == '土豆种植笔记'
    assert reopened.list('土豆')['total'] == 1
    assert reopened.list(kind='web')['total'] == 0
    assert reopened.list('%')['total'] == 0
    assert 'content' not in reopened.list()['items'][0]
    changed = store.update(source['id'], 1, '新版笔记', '春季种植')
    assert changed['revision'] == 2 and changed['status'] == 'pending_build'
    with pytest.raises(ValidationError, match='STALE_REVISION'):
        store.update(source['id'], 1, '冲突', '旧内容')
    with pytest.raises(ValidationError, match='STALE_REVISION'):
        store.delete(source['id'], 1)
    store.delete(source['id'], 2)
    assert store.list()['total'] == 0
    with pytest.raises(ValidationError, match='NOT_FOUND'):
        reopened.get(source['id'])


def test_html_is_preserved_but_preview_removes_active_content(tmp_path):
    store = library.LibraryStore(tmp_path / 'library.sqlite3')
    html = '<title>Wiki 笔记</title><script>alert(1)</script><h1>土豆</h1><p>原文依据</p>'
    item = store.create(upload(html, 'wiki.html'))
    assert item['title'] == 'Wiki 笔记' and item['content'] == html
    assert '原文依据' in item['text_content'] and 'alert' not in item['text_content']


@pytest.mark.parametrize('content,filename,reason', [
    ('', 'a.txt', 'EMPTY'), ('x\0y', 'a.txt', 'EMPTY'),
    ('{invalid', 'a.json', 'INVALID_JSON'), ('text', 'a.pdf', 'UNSUPPORTED'),
    ('text', '../a.txt', 'FILENAME'), ('x' * (library.MAX_BYTES + 1), 'a.txt', 'SIZE_LIMIT'),
])
def test_invalid_files_are_not_inserted(tmp_path, content, filename, reason):
    store = library.LibraryStore(tmp_path / 'library.sqlite3')
    with pytest.raises(ValidationError, match=reason):
        store.create(upload(content, filename))
    assert store.list()['total'] == 0


@pytest.mark.parametrize('url', ['http://example.org', 'file:///etc/passwd', 'https://user:pass@example.org', 'https://example.org:8080'])
def test_url_scheme_and_authority(url):
    with pytest.raises(ValidationError, match='INVALID_URL'):
        library.validate_url(url)


@pytest.mark.parametrize('ip', ['127.0.0.1', '10.1.2.3', '169.254.169.254', '::1', '192.168.0.1'])
def test_private_dns_cannot_be_fetched(monkeypatch, ip):
    monkeypatch.setattr(library.socket, 'getaddrinfo', lambda *a, **k: [(None, None, None, None, (ip, 443))])
    def forbidden(*args, **kwargs):
        pytest.fail('Must reject before connecting')
    monkeypatch.setattr(library.socket, 'create_connection', forbidden)
    with pytest.raises(ValidationError, match='PRIVATE_URL'):
        library.fetch_webpage('https://example.org')


def test_web_import_saves_a_frozen_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(library, 'fetch_webpage', lambda url: {'url': url, 'filename': 'webpage.html', 'content': '<title>土豆百科</title><p>春季作物</p>'})
    store = library.LibraryStore(tmp_path / 'library.sqlite3')
    row = store.create({'kind': 'web', 'url': 'https://example.org/potato'})
    assert row['title'] == '土豆百科' and row['kind'] == 'web'
    assert store.list('春季', 'web')['total'] == 1
    store.update(row['id'], 1, row['title'], '<p>修改本地副本</p>')
    assert store.get(row['id'])['url'] == row['url']


def test_http_library_works_without_snapshot_and_requires_csrf(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'TaskStore', lambda: TaskStore(tmp_path / 'tasks.sqlite3'))
    monkeypatch.setattr(server, 'LibraryStore', lambda: library.LibraryStore(tmp_path / 'library.sqlite3'))
    def no_snapshot(self):
        raise ValidationError('NO_RELEASED_SNAPSHOT')
    monkeypatch.setattr(server.Workbench, 'snapshot', no_snapshot)
    instance = server.make_server(port=0)
    worker = threading.Thread(target=instance.serve_forever, daemon=True)
    worker.start()
    url = f'http://127.0.0.1:{instance.server_port}'
    try:
        with httpx.Client(base_url=url, trust_env=False) as client:
            boot = client.get('/api/bootstrap').json()
            headers = {'Origin': url, 'X-CSRF-Token': boot['csrf']}
            assert client.post('/api/library/create', json=upload()).status_code == 403
            row = client.post('/api/library/create', headers=headers, json=upload()).json()
            assert client.get('/api/library').json()['total'] == 1
            assert client.get('/api/library/source', params={'id': row['id']}).json()['content'] == '土豆种植笔记'
            assert client.post('/api/library/delete', headers=headers, json={'id': row['id'], 'revision': 1}).status_code == 200
            assert client.get('/api/library').json()['total'] == 0
    finally:
        instance.shutdown()
        instance.server_close()
        worker.join(timeout=5)
