import pytest
from stardew_agent.core import ROOT, ValidationError
from stardew_agent.knowledge import Snapshot
from stardew_agent.retrieval import Retriever
from stardew_agent.reranking import rerank

@pytest.fixture(scope='module')
def s():return Snapshot(allow_candidate=True)

def region(s):
    a=next(a for a in s.domain['assets'] if a['url'].endswith('/Kale.png'))
    return {'region_id':'synthetic:query', 'path':a['path'],'sha256':a['sha256']}

def test_same_question_pixel_ranker_used_by_bq_and_d(s):
    calls=[]
    class Model:
        def structured(self,prompt,*,context,images,label):
            calls.append((prompt,context,images))
            assert 1<=len(images)<=4 and all(p.is_file() for p in images)
            assert 'traversed' not in str(context) and 'distance' not in str(context)
            ids=[r['id'] for r in context['candidates']]
            return {'status':'OK','parsed':{'ranked_ids':ids[::-1], 'visual_consistency':'ambiguous'},'execution_mode':'synthetic_fixture'}
    for method in ('BQ','D'):
        r=Retriever(s).retrieve('甘蓝生长条件',entity_ids=['entity:Kale'],method=method,candidate=True,query_regions=[region(s)],rerank_model=Model())
        assert r['trace']['reranker']=='chatecnu_question_pixel_rerank/v1'
        assert r['trace']['rerank_trace']['visual_consistency']=='ambiguous'
        assert r['trace']['budget_used']['rerank_model_requests']==0
    assert calls[0][0]==calls[1][0]

@pytest.mark.parametrize('bad',['foreign_id','duplicate','error'])
def test_invalid_model_ranking_does_not_change_candidate_set(s,bad):
    rows=s.domain['facts'][:3]
    class Model:
        def structured(self,*args,**kwargs):
            return {'status':'API_ERROR' if bad=='error' else 'OK','parsed':{'ranked_ids':['not_in_pool'] if bad=='foreign_id' else [rows[0]['id']]*2,'visual_consistency':'consistent'},'execution_mode':'synthetic_fixture'}
    ranked,trace=rerank(s,rows,'test',{},[],[region(s)],Model())
    assert ranked==rows and trace['degraded_reason']=='MODEL_ERROR_OR_INVALID_RANKING'

def test_changed_pixels_rejected_before_model(s):
    r=region(s);r['sha256']='0'*64
    with pytest.raises(ValidationError,match='RERANK_IMAGE_CHANGED'):
        rerank(s,s.domain['facts'][:3],'test',{},[],[r],object())

def test_without_model_is_explicit_degraded_mode(s):
    rows=s.domain['facts'][:3]
    ranked,trace=rerank(s,rows,'test',{},[],[region(s)],None)
    assert ranked==rows and trace['degraded_reason']=='NO_VISUAL_MODEL' and trace['model_requests']==0

def test_agent_passes_only_registered_task_regions(s,tmp_path):
    from stardew_agent.agent import Agent
    from stardew_agent.state import TaskStore
    from stardew_agent.online_vision import ImageStore
    tasks=TaskStore(tmp_path/'tasks.sqlite3');task=tasks.create(s.id);source=region(s);images=ImageStore()
    upload=images.upload((ROOT/source['path']).read_bytes(),task['task_id'])
    r=images.region(upload['image_id'],task['task_id'],[0,0,1,1])
    tasks.invalidate(task['task_id'],0,'test_query_registered',uploaded_images=[upload],selected_regions=[r])
    class Model:
        def structured(self,*args,context,**kw):
            assert context['query_regions'][0]['region_id']==r['region_id']
            return {'status':'OK','parsed':{'ranked_ids':[x['id'] for x in context['candidates']], 'visual_consistency':'ambiguous'},'execution_mode':'synthetic_fixture'}
    agent=Agent(tasks,Model())
    out=agent.dispatch('retrieve_knowledge',{'query':'甘蓝生长','entity_ids':['entity:Kale']},task['task_id'],s,'')
    assert out['trace']['reranker']=='chatecnu_question_pixel_rerank/v1'
    with pytest.raises(ValidationError,match='UNKNOWN_OR_EXCESS_QUERY_REGIONS'):
        agent.dispatch('retrieve_knowledge',{'query':'test','region_ids':['../../.env']},task['task_id'],s,'')
