import threading
import httpx
import pytest
import stardew_agent.server as server
from stardew_agent.auth import AuthStore
from stardew_agent.core import ValidationError


def test_accounts_and_session_revocation(tmp_path):
    store=AuthStore(tmp_path/'users.sqlite3')
    store.register('manager','test-password-123',setup=True)
    with pytest.raises(ValidationError):store.register('intruder','test-password-123',setup=True)
    store.register('resident','test-password-123')
    token=store.login('resident','test-password-123')
    cookie='pelican_session='+token
    user=store.user(cookie)
    assert user['role']=='user'
    store.own('task','mine',user)
    assert store.allowed('task','mine',user)
    assert not store.allowed('task','someone-else',user)
    store.logout(cookie)
    assert store.user(cookie) is None
    with store.connect() as db:
        assert db.execute('SELECT password_hash FROM users LIMIT 1').fetchone()[0]!='test-password-123'


def test_http_authorization(tmp_path,monkeypatch):
    store=AuthStore(tmp_path/'users.sqlite3')
    monkeypatch.setattr(server,'AuthStore',lambda:store)
    class Stub:
        token='test-csrf'
        def get(self,path,q):return {'ok':True}
    monkeypatch.setattr(server,'Workbench',Stub)
    app=server.make_server(port=0)
    thread=threading.Thread(target=app.serve_forever,daemon=True);thread.start()
    try:
        url=f'http://127.0.0.1:{app.server_port}'
        with httpx.Client(base_url=url,headers={'Origin':url,'X-CSRF-Token':'test-csrf'}) as client:
            assert client.get('/api/review').status_code==401
            assert client.post('/api/auth/register',json={'username':'early_user','password':'test-password-123'}).status_code==200
            assert client.get('/api/auth').json()['user']['role']=='user'
            store.register('manager','test-password-123',setup=True)
            assert client.post('/api/auth/setup',json={'username':'intruder','password':'test-password-123'}).status_code!=200
            assert client.post('/api/auth/login',json={'username':'manager','password':'test-password-123'}).status_code==200
            assert client.get('/api/review').status_code==200
            assert client.post('/api/auth/logout',json={}).status_code==200
            assert client.get('/api/review').status_code==401
            assert client.post('/api/auth/register',json={'username':'resident','password':'test-password-123','role':'admin'}).status_code==200
            assert client.get('/api/auth').json()['user']['role']=='user'
            for endpoint in ('review','evaluations'):
                assert client.get('/api/'+endpoint).status_code==403
            for endpoint in ('review','publish','rule-review'):
                assert client.post('/api/'+endpoint,json={}).status_code==403
            assert client.get('/api/task?id=other').status_code==403
            assert client.post('/api/library/delete',json={'id':'other'}).status_code==403
    finally:
        app.shutdown();app.server_close();thread.join()
