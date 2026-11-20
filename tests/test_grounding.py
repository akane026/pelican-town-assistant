import json
import pytest
from stardew_agent.agent import grounding_check,repair_answer

ANSWER={'answer_text':'剩余9个价值315g，已经没有多余物品可卖。','claim_evidence_refs':[],'calculation_trace_refs':['calc:synthetic']}
CALCS={'calc:synthetic':{'run_id':'calc:synthetic','rule_id':'sale_value','user_inputs':{'quantity':9},'outputs':{'quantity':9,'sales_g':315}}}

def test_semantic_issue_can_trigger_one_repair_without_bad_numbers():
    class Model:
        def call(self,messages,**kw):
            data=json.loads(messages[-1]['content']);assert data['validation_errors']['semantic_issues']
            return {'status':'OK','content':json.dumps({**ANSWER,'answer_text':'候选计算：剩余9个，销售315g。'})}
    answer,report=repair_answer(Model(),ANSWER,{},CALCS,{},extra_errors=[{'claim':'没有多余物品可卖','reason':'contradicts remaining stock'}])
    assert report['accepted'] and '没有' not in answer['answer_text']
    assert ANSWER['answer_text'].endswith('可卖。')

@pytest.mark.parametrize('parsed',[{'verdict':'supported','issues':[{'claim':'x','reason':'contradiction'}]}, {'verdict':'supported'}, {'verdict':'invented','issues':[]}])
def test_malformed_or_contradictory_check_never_passes(parsed):
    class Model:
        def structured(self,*a,**kw):return {'status':'OK','parsed':parsed,'execution_mode':'synthetic_fixture'}
    check=grounding_check(Model(),ANSWER,{},CALCS,{})
    assert check['verdict']=='uncertain' and check['status']=='INVALID_CHECK_JSON'

def test_checker_gets_cited_outputs_not_hidden_graph_or_all_evidence():
    class Model:
        def structured(self,prompt,*,context,**kw):
            assert context['cited_evidence']==[] and context['cited_calculations'][0]['outputs']['sales_g']==315
            assert 'hidden_fact' not in str(context)
            return {'status':'OK','parsed':{'verdict':'unsupported','issues':[{'claim':'no surplus','reason':'9 remain'}]},'execution_mode':'synthetic_fixture'}
    check=grounding_check(Model(),ANSWER,{'hidden_fact':{'value':999}},CALCS,{})
    assert check['verdict']=='unsupported' and check['human_approval'] is False

@pytest.mark.parametrize('check_status',['OK','API_ERROR'])
def test_agent_never_promotes_failed_semantics_to_candidate_answer(tmp_path,check_status):
    from stardew_agent.knowledge import Snapshot
    from stardew_agent.state import TaskStore
    from stardew_agent.agent import Agent
    s=Snapshot(allow_candidate=True);fact=next(f for f in s.domain['facts'] if f['subject']=='entity:Kale' and f['predicate']=='sell_normal')
    store=TaskStore(tmp_path/'tasks.db');task=store.create(s.id)
    draft={'answer_text':'甘蓝110g，所有作物都是110g。','claim_evidence_refs':[fact['id']],'calculation_trace_refs':[]}
    class Model:
        def __init__(self):self.rounds=0;self.repairs=0;self.checks=0
        def call(self,*a,**kw):
            if kw['label']=='v3_answer_repair':
                self.repairs+=1;return {'status':'OK','content':json.dumps(draft)}
            self.rounds+=1
            if self.rounds==1:return {'status':'OK','tool_calls':[{'id':'t','function':{'name':'get_evidence','arguments':json.dumps({'record_id':fact['id']})}}]}
            return {'status':'OK','content':json.dumps(draft)}
        def structured(self,*a,**kw):
            self.checks+=1
            return {'status':check_status,'parsed':{'verdict':'unsupported','issues':[{'claim':'all crops','reason':'only one entity is evidenced'}]},'execution_mode':'synthetic_fixture','reason':'injected_failure' if check_status!='OK' else None}
    model=Model();answer=Agent(store,model).run(task['task_id'],'甘蓝的普通售价？')
    assert answer['status']=='ANSWER_VALIDATION_FAILED' and model.repairs<=1 and model.checks<=2
    assert not answer['grounding_checks'][-1]['human_approval']

@pytest.mark.parametrize('raw',['[1]','null','"text"'])
def test_json_nonobject_response_is_a_controlled_failure(tmp_path,raw):
    from stardew_agent.knowledge import Snapshot
    from stardew_agent.state import TaskStore
    from stardew_agent.agent import Agent
    store=TaskStore(tmp_path/'tasks.db');task=store.create(Snapshot(allow_candidate=True).id)
    class Model:
        def call(self,*a,**kw):return {'status':'OK','content':raw}
    assert Agent(store,Model(),max_rounds=2).run(task['task_id'],'test')['status']=='ANSWER_VALIDATION_FAILED'

def test_midloop_state_change_invalidates_previous_evidence(tmp_path):
    from stardew_agent.knowledge import Snapshot
    from stardew_agent.state import TaskStore
    from stardew_agent.agent import Agent
    s=Snapshot(allow_candidate=True);fact=next(f for f in s.domain['facts'] if f['subject']=='entity:Kale' and f['predicate']=='sell_normal')
    store=TaskStore(tmp_path/'tasks.db');task=store.create(s.id)
    class Model:
        def __init__(self):self.round=0
        def call(self,*a,**kw):
            self.round+=1
            if self.round==1:name,args='get_evidence',{'record_id':fact['id']}
            elif self.round==2:name,args='update_task_state',{'fields':{'quantity':8},'evidence_quote':'改成8个'}
            else:return {'status':'OK','content':json.dumps({'answer_text':'110g','claim_evidence_refs':[fact['id']],'calculation_trace_refs':[]})}
            return {'status':'OK','tool_calls':[{'id':str(self.round),'function':{'name':name,'arguments':json.dumps(args)}}]}
    answer=Agent(store,Model(),max_rounds=4).run(task['task_id'],'原来12个，改成8个')
    assert answer['status']=='ANSWER_VALIDATION_FAILED' and answer['validation_errors']['invalid_references']

def test_reading_state_alone_cannot_license_a_memory_answer(tmp_path):
    from stardew_agent.knowledge import Snapshot
    from stardew_agent.state import TaskStore
    from stardew_agent.agent import Agent
    store=TaskStore(tmp_path/'tasks.db');task=store.create(Snapshot(allow_candidate=True).id)
    class Model:
        def __init__(self):self.round=0
        def call(self,*a,**kw):
            self.round+=1
            if self.round==1:return {'status':'OK','tool_calls':[{'id':'s','function':{'name':'read_task_state','arguments':'{}'}}]}
            return {'status':'OK','content':json.dumps({'answer_text':'我记得这种作物可以在任何季节生长。','claim_evidence_refs':[],'calculation_trace_refs':[]})}
    answer=Agent(store,Model(),max_rounds=3).run(task['task_id'],'生长条件是什么？')
    assert answer['status']=='ANSWER_VALIDATION_FAILED' and answer['validation_errors']['missing_support']
