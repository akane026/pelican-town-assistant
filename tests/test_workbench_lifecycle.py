import base64,io
import pytest
from PIL import Image
from stardew_agent.server import Workbench
from stardew_agent.state import TaskStore
from stardew_agent.core import ValidationError

def test_roi_and_cancel_invalidate_complete_answer(tmp_path):
    app=Workbench();app.tasks=TaskStore(tmp_path/'api-state.sqlite3')
    task=app.post('/api/task',{});tid=task['task_id']
    app.tasks.save_runtime(tid,0,answer={'answer_text':'stale'},last_bundle_id='stale',results=['calculation:stale'],missing_inputs=['day'])
    stream=io.BytesIO();Image.new('RGB',(20,20),'lime').save(stream,format='PNG')
    upload=app.post('/api/upload',{'task_id':tid,'data':base64.b64encode(stream.getvalue()).decode()})
    app.post('/api/region',{'task_id':tid,'revision':0,'image_id':upload['image_id'],'bbox':[.1,.1,.9,.9]})
    current=app.tasks.get(tid)
    assert current['revision']==1 and not current['results']
    assert not set(('answer','last_bundle_id','missing_inputs'))&set(current)
    assert 'calculation:stale' in current['stale_result_ids']
    with pytest.raises(ValidationError,match='STALE_TASK_REVISION'):
        app.post('/api/cancel',{'task_id':tid,'revision':0})
    result=app.post('/api/cancel',{'task_id':tid,'revision':1})
    assert result['status']=='CANCELLED' and result['revision']==2

def test_task_knowledge_lookup_does_not_read_latest_candidate(tmp_path,monkeypatch):
    app=Workbench();app.tasks=TaskStore(tmp_path/'bound.sqlite3')
    task=app.post('/api/task',{});sid=task['snapshot_id'];tid=task['task_id']
    def forbidden():raise AssertionError('historical task read latest candidate')
    monkeypatch.setattr(app,'snapshot',forbidden)
    graph=app.get('/api/graph',{'task_id':tid,'id':'entity:Kale'})
    assert graph['snapshot_id']==sid
    record=app.get('/api/record',{'task_id':tid,'id':'entity:Kale'})
    assert record['snapshot_id']==sid
    availability=app.get('/api/capabilities',{'task_id':tid})
    assert availability['snapshot_id']==sid and availability['task_revision']==0
    assert availability['status']!='AVAILABLE'
