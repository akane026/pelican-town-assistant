import json,threading
import pytest,httpx
from stardew_agent.core import *
from stardew_agent.knowledge import Snapshot
from stardew_agent.state import TaskStore
from stardew_agent.server import make_server
from stardew_agent.agent import Agent
from stardew_agent.online_vision import ImageStore

@pytest.fixture(scope='module')
def snapshot():return Snapshot(allow_candidate=True)

def test_no_external_bind():
    with pytest.raises(ValidationError,match='LOOPBACK'):make_server('0.0.0.0')

def test_api_origin_csrf_and_secret_boundary(tmp_path):
    server=make_server(port=0);server.app.tasks=TaskStore(tmp_path/'api.sqlite3');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url=f'http://127.0.0.1:{server.server_port}'
    try:
        with httpx.Client(base_url=url,trust_env=False) as c:
            boot=c.get('/api/bootstrap');assert boot.status_code==200
            assert 'CHATECNU_API_KEY' not in boot.text and 'api_key' not in boot.text
            assert c.get('/api/bootstrap',headers={'Host':'attacker.example'}).status_code==403
            assert c.post('/api/task',json={}).status_code==403
            h={'Origin':url,'X-CSRF-Token':boot.json()['csrf']}
            assert c.post('/api/task',headers={**h,'Origin':'https://attacker.example'},json={}).status_code==403
            task=c.post('/api/task',headers=h,json={}).json();tid=task['task_id']
            assert c.get('/api/task',params={'id':tid}).json()['task']['revision']==0
            assert c.post('/api/state',headers=h,json={'task_id':tid,'revision':0,'fields':{'quantity':3}}).status_code==200
            assert c.post('/api/state',headers=h,json={'task_id':tid,'revision':0,'fields':{'quantity':4}}).status_code==400
            assert c.get('/api/image',params={'id':'../../.env'}).status_code==400
            assert c.get('/.env').status_code==404
            assert c.post('/api/review',headers=h,json={'id':'forged','snapshot_id':boot.json()['snapshot']['snapshot_id'],'action':'approve','reason':'test'}).status_code==400
            out=c.get('/api/export',params={'id':tid,'format':'md'});assert out.status_code==200 and '# 星露谷助手任务导出' in out.text
    finally:server.shutdown();server.server_close()

@pytest.mark.parametrize('reason',['ReadTimeout','HTTP_429'])
def test_model_error_distinct_from_unknown_knowledge(snapshot,tmp_path,reason):
    class Failed:
        def call(self,*a,**kw):return {'status':'API_ERROR','reason':reason}
    tasks=TaskStore(tmp_path/'error.db');t=tasks.create(snapshot.id)
    r=Agent(tasks,Failed()).run(t['task_id'],'资料中有没有甘蓝？')
    assert r['status']=='MODEL_ERROR' and r['reason']==reason and not r['tool_events']

def test_malformed_json_is_not_an_answer(snapshot,tmp_path):
    class Failed:
        def call(self,*a,**kw):return {'status':'OK','content':'{invalid','finish_reason':'stop'}
    tasks=TaskStore(tmp_path/'json.db');t=tasks.create(snapshot.id)
    r=Agent(tasks,Failed(),max_rounds=2).run(t['task_id'],'测试')
    assert r['status']=='ANSWER_VALIDATION_FAILED' and not r['calculation_traces']

def test_corrupt_image_and_registry_path_rejected():
    with pytest.raises(ValidationError,match='INVALID_IMAGE'):ImageStore().upload(b'not a picture','synthetic')
    with pytest.raises(ValidationError,match='INVALID_IMAGE_ID'):ImageStore().get('upload:../../.env','synthetic')

def test_inventory_identity_case_and_infeasible_guard(snapshot):
    from test_runtime import prepared
    from stardew_agent.calculations import execute
    p={'entity_id':'entity:Spring_Crops_Bundle','inventory':{k:{'normal':n} for k,n in [('parsnip',10),('green_bean',1),('cauliflower',1),('potato',1)]},'completed':[]}
    r=execute('bundle_reserve',prepared(snapshot,'bundle_reserve',p),p)
    assert r['outputs']['options'][0]['remaining']['Parsnip']['normal']==9
    p['completed']=False
    assert execute('bundle_reserve',prepared(snapshot,'bundle_reserve',p),p)['status']=='INVALID_INPUT'

def test_document_pixel_and_context_cache_keys_separate(snapshot):
    from stardew_agent.model import ModelClient
    c=ModelClient(offline=True);a=snapshot.domain['assets'][:2]
    first=c.structured('synthetic cache isolation test',images=[ROOT/a[0]['path']],context={'role':'stage1'})
    other=c.structured('synthetic cache isolation test',images=[ROOT/a[1]['path']],context={'role':'stage1'})
    context=c.structured('synthetic cache isolation test',images=[ROOT/a[0]['path']],context={'role':'stage2'})
    assert len({x['cache_key'] for x in [first,other,context]})==3
    assert all(x['execution_mode']=='offline' for x in [first,other,context])
