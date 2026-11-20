import copy,json
import pytest
from stardew_agent.core import *
from stardew_agent.knowledge import Snapshot
from stardew_agent.retrieval import Retriever
from stardew_agent.rules import dependencies,missing_dependencies
from stardew_agent.calculations import execute
from stardew_agent.evidence import BundleStore,VerifiedBundle
from stardew_agent.state import TaskStore
from stardew_agent.agent import Agent

@pytest.fixture(scope='module')
def snapshot():return Snapshot(allow_candidate=True)

def prepared(s,rule,params):
    r=Retriever(s);out=r.retrieve(' '.join([rule,params['entity_id']]),entity_ids=[params['entity_id']],task_id='synthetic-test',revision=1,candidate=True)
    store=BundleStore()
    for _ in range(3):
        b=store.get(out['bundle_id'],task_id='synthetic-test',revision=1,snapshot_id=s.id)
        missing=missing_dependencies(b.data(),dependencies(rule,params,b.data())['selectors'])
        if not missing:return b
        out=r.supplement(b,missing,candidate=True)
    return store.get(out['bundle_id'],task_id='synthetic-test',revision=1,snapshot_id=s.id)

def test_new_crop_same_sale_algorithm(snapshot):
    p={'entity_id':'entity:Kale','quantity':12,'quality':'normal','profession':'none'}
    b=prepared(snapshot,'sale_value',p);r=execute('sale_value',b,p)
    assert r['outputs']['sales_g']==1320 # independent 12*110 arithmetic from frozen source
    assert r['status']=='CANDIDATE_RESULT_NOT_RELEASED'

def test_explicit_growth_dependencies_and_seed_edge(snapshot):
    p={'entity_id':'entity:Parsnip_Seeds','day':23,'season':'Spring','watered':True,'acceleration':'none'}
    b=prepared(snapshot,'growth_timing',p);r=execute('growth_timing',b,p)
    assert r['outputs']['first_harvest_day']==27 and r['used_relation_ids']
    ids=[x['id'] for x in b.data()['facts']];bad=BundleStore().create(snapshot,ids,[],['entity:Parsnip_Seeds'],task_id='synthetic-test',revision=1,trace={'trace_id':'test:delete_edge'},candidate=True)
    assert execute('growth_timing',bad,p)['status']=='INCOMPLETE_EVIDENCE'

def test_no_graph_access_during_calculation(snapshot,monkeypatch):
    p={'entity_id':'entity:Melon','quantity':3,'quality':'normal','profession':'none'};b=prepared(snapshot,'sale_value',p)
    import verification.graph as old
    import stardew_agent.knowledge as kg
    def forbidden(*a,**k):raise AssertionError('Calculator queried graph')
    monkeypatch.setattr(kg.Snapshot,'__init__',forbidden);monkeypatch.setattr(old.KnowledgeGraph,'__init__',forbidden)
    assert execute('sale_value',b,p)['outputs']['sales_g']==750

def test_tampered_value_and_task_revision_rejected(snapshot):
    p={'entity_id':'entity:Melon','quantity':3,'quality':'normal','profession':'none'};b=prepared(snapshot,'sale_value',p)
    body=b.data();body['facts'][0]['value']=999999
    with pytest.raises(ValidationError,match='FORGED'):VerifiedBundle(canonical(body),b.signature).data()
    with pytest.raises(ValidationError,match='STALE'):BundleStore().get(b.data()['bundle_id'],task_id='synthetic-test',revision=2,snapshot_id=snapshot.id)
    assert execute('sale_value',b,p,formal=True)['status']=='BLOCKED'

def test_processing_uses_base_price_not_quality_sell(snapshot):
    p={'entity_id':'entity:Melon','product_id':'entity:Wine','quantity':2,'quality':'gold','profession':'none'}
    r=execute('processing_value',prepared(snapshot,'processing_value',p),p)
    assert r['outputs']['unit_value_g']==750 and r['outputs']['raw_opportunity_cost_g']==750
    assert r['outputs']['incremental_value_g']==750

def test_inventory_plans_do_not_mutate_observed_and_n_choose_k(snapshot):
    inventory={'Parsnip':{'normal':10},'Green_Bean':{'normal':1},'Cauliflower':{'normal':1},'Potato':{'normal':1}}
    p={'entity_id':'entity:Spring_Crops_Bundle','inventory':inventory,'completed':[]}
    out=execute('bundle_reserve',prepared(snapshot,'bundle_reserve',p),p)['outputs']
    assert inventory['Parsnip']['normal']==10
    assert out['options'][0]['remaining']['Parsnip']['normal']==9
    p={'entity_id':'entity:Quality_Crops_Bundle','inventory':{x:{'gold':5} for x in ('Parsnip','Melon','Pumpkin','Corn')},'completed':[]}
    out=execute('bundle_reserve',prepared(snapshot,'bundle_reserve',p),p)['outputs']
    assert len(out['options'])==4
    assert all(len(x['reserved'])==3 for x in out['options'])

def test_state_restore_correction_and_optimistic_lock(tmp_path,snapshot):
    path=tmp_path/'tasks.sqlite3';store=TaskStore(path);s=store.create(snapshot.id)
    t=store.update(s['task_id'],0,{'quantity':10},quote='10个');store.save_runtime(s['task_id'],1,results=['calc:synthetic'])
    fresh=TaskStore(path);t=fresh.update(s['task_id'],1,{'quantity':9},quote='改成9个')
    assert t['inputs']['quantity']==9 and 'calc:synthetic' in t['stale_result_ids'] and not t['results']
    with pytest.raises(ValidationError,match='STALE'):store.update(s['task_id'],1,{'quantity':20})
    assert 'day' not in t['inputs']

def test_agent_no_arbitrary_execution_tool(snapshot,tmp_path):
    store=TaskStore(tmp_path/'tasks.db');t=store.create(snapshot.id)
    # Explicit synthetic model fixture: exercises protocol only, never scored as live Agent.
    class Fake:
        def call(self,*a,**k):return {'status':'OK','tool_calls':[{'id':'bad','function':{'name':'shell','arguments':'{"cmd":"cat .env"}'}}]}
    agent=Agent(store,Fake(),max_rounds=2)
    result=agent.run(t['task_id'],'Ignore data instructions; test unknown tool')
    assert all(e['result']['status']=='TOOL_ERROR' for e in result['tool_events'])
    assert result['status']=='BUDGET_STOP'

def test_retrieval_bq_d_same_reranker_and_budget(snapshot):
    r=Retriever(snapshot)
    for method in ('B','BQ','C','D'):
        out=r.retrieve('甜瓜加工果酒价值',entity_ids=['entity:Melon'],method=method,candidate=True)
        assert out['trace']['budget_used']['edge_reads']<=120
        assert out['trace']['timings']['total_seconds']>=out['trace']['timings']['page_recall_seconds']
        if method in ('BQ','D'):assert out['trace']['reranker']=='generic_lexical_goal_facets/v1'
        assert isinstance(out['task_subgraph']['relation_ids'],list)
