"""Scripted model fixtures exercise real tools; these are not live model scores."""
import json
import pytest
from stardew_agent.agent import Agent,validate_answer,repair_knowledge_sections,STATE_FIELDS
from stardew_agent.core import ValidationError
from stardew_agent.knowledge import Snapshot
from stardew_agent.state import TaskStore
from stardew_agent.answer_rendering import calculation_answer

REQUEST='解释甘蓝的普通售价，并算3个普通甘蓝的售价；无职业。'
P={'entity_id':'entity:Kale','quantity':3,'quality':'normal','profession':'none'}

def call(name,args):return {'status':'OK','execution_mode':'synthetic_fixture','tool_calls':[{'id':name,'function':{'name':name,'arguments':json.dumps(args)}}]}

class MixedModel:
    def __init__(self,fact,sections=True,supported=True):self.round=0;self.fact=fact;self.sections=sections;self.supported=supported;self.bundle=None
    def call(self,messages,**kw):
        self.round+=1
        if self.round==1:return call('set_task_goals',{'goals':[
            {'id':'why','kind':'explanation','user_quote':'解释甘蓝的普通售价','entity_id':'entity:Kale','predicates':['sell_normal']},
            {'id':'sale','kind':'calculation','user_quote':'算3个普通甘蓝的售价','entity_id':'entity:Kale','rule_ids':['sale_value'],'params':{'quantity':3,'quality':'normal','profession':'none'}}]})
        if self.round==2:return call('update_task_state',{'fields':P,'evidence_quote':REQUEST})
        if self.round==3:return call('retrieve_knowledge',{'query':'甘蓝 普通售价','entity_ids':['entity:Kale']})
        if self.round==4:
            self.bundle=json.loads(messages[-1]['content'])['bundle_id']
            return call('fetch_dependencies',{'rule_id':'sale_value','bundle_id':self.bundle,'params':P})
        if self.round==5:
            self.bundle=json.loads(messages[-1]['content'])['bundle_id']
            return call('execute_rule',{'rule_id':'sale_value','bundle_id':self.bundle,'params':P,'goal_id':'sale'})
        answer={'answer_text':'已全部完成。','claim_evidence_refs':[],'calculation_trace_refs':[],'status':'ANSWERED'}
        if self.sections:answer['knowledge_sections']=[{'goal_id':'why','text':'甘蓝的普通售价为110g。','evidence_refs':[self.fact['id']]}]
        return {'status':'OK','content':json.dumps(answer)}
    def structured(self,prompt,**kw):
        # Retrieval may use the same model interface; its invalid-rerank fallback
        # is permitted. This response only certifies synthetic checker behavior.
        return {'status':'OK','parsed':{'verdict':'supported' if self.supported else 'unsupported','issues':[] if self.supported else [{'claim':'fixture','reason':'unsupported fixture'}]},'execution_mode':'synthetic_fixture'}

@pytest.mark.parametrize('sections,supported,expected',[(True,True,'CANDIDATE_ANSWER'),(False,True,'PARTIAL_ANSWER'),(True,False,'PARTIAL_ANSWER')])
def test_mixed_answer_keeps_checked_explanation_and_real_calculation(tmp_path,sections,supported,expected):
    s=Snapshot(allow_candidate=True);fact=next(f for f in s.domain['facts'] if f['subject']=='entity:Kale' and f['predicate']=='sell_normal')
    store=TaskStore(tmp_path/'tasks.db');t=store.create(s.id)
    result=Agent(store,MixedModel(fact,sections,supported),retrieval_method='B').run(t['task_id'],REQUEST)
    assert result['status']==expected,result
    assert result['calculation_traces'][0]['outputs']['sales_g']==330
    assert '330g' in result['answer_text']
    assert ('甘蓝的普通售价为110g。' in result['answer_text'])==(sections and supported)
    assert result['goal_coverage']['complete']==(sections and supported)
    assert result['execution_mode']=='candidate_diagnostic' and not result['goal_coverage']['independently_verified']
    trace=next(e['result']['trace'] for e in result['tool_events'] if e['tool']=='retrieve_knowledge')
    assert trace['method']=='B'
    assert all(e['model_execution_mode']=='synthetic_fixture' for e in result['tool_events'])

def test_cancel_in_a_batch_prevents_every_later_tool(tmp_path):
    s=Snapshot(allow_candidate=True);store=TaskStore(tmp_path/'tasks.db');t=store.create(s.id)
    class Model:
        def call(self,*a,**k):return {'status':'OK','tool_calls':[call('read_task_state',{})['tool_calls'][0],call('discover_rules',{'goal':'must not run'})['tool_calls'][0]]}
    class CancelDuringTool(Agent):
        def dispatch(self,*a,**k):
            result=super().dispatch(*a,**k);current=store.get(t['task_id']);store.cancel(t['task_id'],current['revision']);return result
    result=CancelDuringTool(store,Model()).run(t['task_id'],'测试取消')
    assert result['status']=='CANCELLED' and len(result['tool_events'])==1 and not result['calculation_traces']
    assert store.get(t['task_id'])['status']=='CANCELLED' and 'answer' not in store.get(t['task_id'])

def test_external_edit_while_model_is_pending_wins(tmp_path):
    s=Snapshot(allow_candidate=True);store=TaskStore(tmp_path/'tasks.db');t=store.create(s.id)
    class Model:
        def call(self,*a,**k):
            state=store.get(t['task_id']);store.update(t['task_id'],state['revision'],{'quantity':5})
            return call('read_task_state',{})
    result=Agent(store,Model()).run(t['task_id'],'初始请求')
    assert result['status']=='STATE_CHANGED' and not result['tool_events']
    assert store.get(t['task_id'])['inputs']['quantity']==5 and 'answer' not in store.get(t['task_id'])

def test_rendering_never_compares_outputs_from_different_plans():
    def result(product,value,plan):return {'rule_id':'processing_value','user_inputs':{**P,'product_id':'entity:'+product},
        'outputs':{'unit_value_g':value,'sales_g':value,'raw_opportunity_cost_g':0,'incremental_value_g':value},'plan_context':{'plan_id':plan}}
    out=calculation_answer({'a':result('Wine',200,'plan:a'),'b':result('Jelly',180,'plan:b')},{},{},candidate=True)
    assert '最高' not in out['answer_text']

def test_repeated_identical_failure_stops_before_round_budget(tmp_path):
    store=TaskStore(tmp_path/'tasks.db');t=store.create(Snapshot(allow_candidate=True).id)
    class Model:
        def call(self,*a,**k):return call('get_evidence',{'record_id':'fact:nonexistent'})
    answer=Agent(store,Model(),max_rounds=12).run(t['task_id'],'查缺失资料')
    assert answer['status']=='REPEATED_FAILURE_STOP' and answer['budget']['rounds_used']==3 and answer['budget']['tool_calls']==3

def test_source_url_digits_are_not_game_values_but_link_labels_are_checked():
    evidence={'fact:123abc':{'subject':'entity:Kale','predicate':'growth_days','value':6}}
    answer={'answer_text':'需6天。出处 [Wiki](https://example.org/?oldid=192520)，事实 fact:123abc。','claim_evidence_refs':['fact:123abc']}
    assert validate_answer(answer,evidence,{}, {})['unsupported_numbers']==[]
    answer['answer_text']='[售价999g](https://example.org/?oldid=192520)'
    assert validate_answer(answer,evidence,{}, {})['unsupported_numbers']==['999']
    answer['answer_text']='https://example.org/?oldid=192520，售价999g。'
    assert validate_answer(answer,evidence,{}, {})['unsupported_numbers']==['999']

@pytest.mark.parametrize('invented',[False,True])
def test_knowledge_repair_keeps_goal_identity_and_cannot_add_values(invented):
    goals={'growth':{'id':'growth','kind':'explanation','entity_id':'entity:Kale','user_quote':'说明生长周期'}}
    evidence={'fact:growth':{'subject':'entity:Kale','predicate':'growth_days','value':6}}
    original=[{'goal_id':'growth','text':'第1日种，第7日收。','evidence_refs':['fact:growth']}]
    class Model:
        def call(self,messages,**kw):
            assert kw['label']=='v3_knowledge_repair'
            packet=json.loads(messages[-1]['content']);assert packet['goals'][0]['id']=='growth'
            text='需要7天。' if invented else '候选证据记载生长周期为6天。'
            return {'status':'OK','content':json.dumps({'knowledge_sections':[{'goal_id':'growth','text':text,'evidence_refs':['fact:growth']}]}),'execution_mode':'synthetic_fixture'}
    repaired,report=repair_knowledge_sections(Model(),original,goals,evidence,{},[{'goal_id':'growth','reason':'unsupported numbers'}])
    assert bool(repaired)==(not invented) and report['accepted']==(not invented)
    assert original[0]['text']=='第1日种，第7日收。' and report['original_sections']==original

def test_model_authority_boundary_and_forged_region_never_reaches_vision(tmp_path,monkeypatch):
    s=Snapshot(allow_candidate=True);store=TaskStore(tmp_path/'tasks.db');t=store.create(s.id);agent=Agent(store,object())
    assert not {'confirmed_entities','selected_regions'}&set(STATE_FIELDS['properties'])
    for fields in ({'confirmed_entities':{'fake':{'entity_id':'entity:Kale'}}},{'selected_regions':[{'path':'.env'}]}):
        result=agent.dispatch('update_task_state',{'fields':fields,'evidence_quote':'用户消息'},t['task_id'],s,'用户消息')
        assert result['status']=='INVALID_STATE_FIELDS'
    fake={'region_id':'user_region:fake','image_id':'upload:fake','bbox':[0,0,1,1],'task_id':t['task_id'],'path':'.env','sha256':'fake'}
    store.save_runtime(t['task_id'],0,selected_regions=[fake])
    def forbidden(*a,**k):raise AssertionError('Unregistered path reached image IO')
    monkeypatch.setattr('stardew_agent.agent.VisualMatcher',forbidden)
    for name,args in [('resolve_visual',{'region_id':fake['region_id']}),('retrieve_knowledge',{'query':'inspect','region_ids':[fake['region_id']]})]:
        with pytest.raises(ValidationError,match='UNREGISTERED_REGION_PATH'):agent.dispatch(name,args,t['task_id'],s,'用户消息')

@pytest.mark.parametrize('via',['get_evidence','retrieve_knowledge'])
def test_raw_source_never_licenses_released_knowledge_answer(tmp_path,monkeypatch,via):
    from stardew_agent.agent import answer_evidence_allowed
    raw={'id':'evidence:synthetic-unreviewed','quote':'Kale grows in Spring.','entity_ids':['entity:Kale']}
    class SyntheticSnapshot:
        id='synthetic-release'
        records={'entities':{'entity:Kale':{'id':'entity:Kale','name':'Kale'}},'facts':{},'relations':{},'alignments':{},'evidence':{raw['id']:raw}}
    monkeypatch.setattr('stardew_agent.agent.Snapshot',lambda *a,**k:SyntheticSnapshot())
    class Sources:
        def __init__(self,*a):self.identity_aliases={'entity:Kale':['甘蓝','Kale']}
        def retrieve(self,*a,**k):return {'bundle_id':'synthetic-bundle','evidence_refs':[raw],'facts':[],'relations':[]}
    monkeypatch.setattr('stardew_agent.agent.Retriever',Sources)
    store=TaskStore(tmp_path/'tasks.db');t=store.create('synthetic-release',mode='released')
    class Model:
        def __init__(self):self.round=0
        def call(self,*a,**kw):
            if kw['label']=='v3_knowledge_repair':return {'status':'OK','content':json.dumps({'knowledge_sections':[]})}
            self.round+=1
            if self.round==1:return call('set_task_goals',{'goals':[{'id':'season','kind':'knowledge','entity_id':'entity:Kale','user_quote':'甘蓝的季节'}]})
            if self.round==2:return call(via,{'record_id':raw['id']} if via=='get_evidence' else {'query':'甘蓝的季节'})
            return {'status':'OK','content':json.dumps({'answer_text':'甘蓝在春季生长。','claim_evidence_refs':[raw['id']],
                'knowledge_sections':[{'goal_id':'season','text':'甘蓝在春季生长。','evidence_refs':[raw['id']]}]})}
        def structured(self,*a,**k):raise AssertionError('Raw source reached formal grounding as semantic authority')
    answer=Agent(store,Model()).run(t['task_id'],'甘蓝的季节')
    assert answer['status']=='PARTIAL_ANSWER' and not answer['goal_coverage']['complete']
    assert answer['provenance_only_refs']==[raw['id']] and not answer['claim_evidence_refs']
    assert not answer_evidence_allowed(raw,'released')
    approved={'id':'fact:synthetic','subject':'entity:Kale','predicate':'season','value':'Spring','answer_allowed':True,'review_status':'approved_human',
              'approval':{'actor':'local_user','action':'approve','reason':'synthetic test fixture, not a production review'}}
    assert answer_evidence_allowed(approved,'released')

def test_alias_catalog_applies_to_resolution_and_correction_without_resetting_other_inputs(tmp_path):
    from stardew_agent.retrieval import Retriever,unique_identity_mention
    s=Snapshot(allow_candidate=True);store=TaskStore(tmp_path/'tasks.db');t=store.create(s.id)
    t=store.update(t['task_id'],t['revision'],{'quantity':2,'quality':'normal','profession':'none'})
    agent=Agent(store,object());catalog=Retriever(s)
    assert 'entity:Jelly' in {r['entity_id'] for r in catalog.resolve('改成果酱')}
    result=agent.dispatch('update_task_state',{'fields':{'product_id':'entity:Jelly'},'evidence_quote':'改成果酱'},t['task_id'],s,'改成果酱')
    assert result['inputs']=={'product_id':'entity:Jelly','quantity':2,'quality':'normal','profession':'none'}
    aliases={f'entity:Shared{i}':['同名',f'entity:Shared{i}'] for i in range(7)}
    assert not unique_identity_mention('entity:Shared6','同名',aliases)
    assert unique_identity_mention('entity:Shared6','同名 entity:Shared6',aliases)
    assert not unique_identity_mention('entity:Shared6','不存在',aliases)
    with pytest.raises(ValidationError,match='STATE_ENTITY_NOT_IN_QUOTE'):
        agent.dispatch('update_task_state',{'fields':{'entity_id':'entity:Kale'},'evidence_quote':'甜瓜'},t['task_id'],s,'甜瓜')

@pytest.mark.parametrize('quote,day,valid',[('春27日',27,True),('春季第 27 天',27,True),('春卷27个',27,False),('春29日',29,False),('春27日',26,False)])
def test_bounded_seasonal_date_alias(quote,day,valid):
    from stardew_agent.state import check_extracted_values
    if valid:check_extracted_values({'season':'Spring','day':day},quote)
    else:
        with pytest.raises(ValidationError):check_extracted_values({'season':'Spring','day':day},quote)


def test_verified_revision_metadata_and_list_labels_do_not_license_game_numbers():
    evidence={'fact:f':{'value':6,'evidence_ids':['evidence:e']},'evidence:e':{'revision_id':'192520'}}
    answer={'answer_text':'1. 生长需6天。修订版192520。','claim_evidence_refs':['fact:f']}
    assert not validate_answer(answer,evidence,{}, {})['unsupported_numbers']
    for text,number in [('2. 售价192520g。','192520'),('修订版192521。','192521'),('1. 第7日成熟。','7'),('1.5天','1.5')]:
        answer['answer_text']=text
        assert number in validate_answer(answer,evidence,{}, {})['unsupported_numbers']


def test_grounding_publication_separate_per_goal_and_explicit_provenance_only():
    from stardew_agent.agent import grounding_check,supported_sections
    evidence={'fact:a':{'id':'fact:a','subject':'entity:Kale','predicate':'season','value':['Spring'],'evidence_ids':['evidence:a'],'answer_allowed':False},
        'fact:b':{'id':'fact:b','subject':'entity:Kale','predicate':'growth_days','value':6,'unit':'growth_nights','evidence_ids':['evidence:b']}}
    provenance={'evidence:a':{'id':'evidence:a','quote':'Spring'},'evidence:b':{'id':'evidence:b','quote':'6 days'},'evidence:hidden':{'id':'evidence:hidden','quote':'must never enter'}}
    sections=[{'goal_id':'season','text':'春季。','evidence_refs':['fact:a']},{'goal_id':'growth','text':'7天。','evidence_refs':['fact:b']}]
    class Checker:
        def structured(self,prompt,context,**kw):
            assert context['publication_policy']['candidate_diagnostic_is_not_publication']
            assert {r['id'] for r in context['supporting_provenance']}=={'evidence:a','evidence:b'}
            assert context['sections'][0]['requirements']['predicates']==['season']
            return {'status':'OK','execution_mode':'synthetic_fixture','parsed':{'section_verdicts':[
                {'goal_id':'season','verdict':'supported','issues':[]},
                {'goal_id':'growth','verdict':'unsupported','issues':[{'claim':'7天','reason':'fact says 6'}]}]}}
    goals=[{'goal':{'id':s['goal_id'],'kind':'knowledge','predicates':['season'] if i==0 else ['growth_days'],'user_quote':'季节和生长期'},'section':s} for i,s in enumerate(sections)]
    check=grounding_check(Checker(),{'answer_text':'test','claim_evidence_refs':['fact:a','fact:b']},evidence,{}, {},goal_constraints=goals,provenance=provenance)
    assert supported_sections(check,sections)==[sections[0]] and not check['human_approval']

@pytest.mark.parametrize('include_basis',[False,True])
def test_unit_definition_requires_explicit_current_basis(include_basis):
    from stardew_agent.agent import grounding_check
    from stardew_agent.capabilities import fact_unit_dependencies
    fact={'id':'fact:growth','subject':'entity:Kale','predicate':'growth_days','value':6,'unit':'growth_nights','evidence_ids':['evidence:growth']}
    basis={'id':'fact:water','subject':'entity:Calendar','predicate':'watered_growth','unit':'condition','value':True,'evidence_ids':['evidence:water']}
    evidence={fact['id']:fact,'evidence:growth':{'id':'evidence:growth','quote':'6 days'}}
    if include_basis:evidence.update({basis['id']:basis,'evidence:water':{'id':'evidence:water','quote':'The grow times assume seeds are watered on the planting day.'}})
    definitions=fact_unit_dependencies({'facts':[fact]},[fact['id']])['unit_definitions']
    class Checker:
        def structured(self,prompt,context,**kw):
            assert bool(context['verified_unit_definitions'])==include_basis
            assert ('fact:water' in {r['id'] for r in context['supporting_provenance']})==include_basis
            return {'status':'OK','parsed':{'verdict':'supported' if include_basis else 'uncertain','issues':[]}}
    grounding_check(Checker(),{'answer_text':'6个有效生长夜晚','claim_evidence_refs':[fact['id']]},evidence,{}, {},unit_definitions=definitions)


def test_clarification_does_not_publish_model_defaults_or_capability_promises(tmp_path):
    store=TaskStore(tmp_path/'tasks.db');t=store.create(Snapshot(allow_candidate=True).id)
    class Model:
        def call(self,*a,**k):return call('request_clarification',{'question':'我按1份、普通品质、无职业估算；给我模组价格就能保证最优排产。','missing_fields':['quantity','quality','profession','mod_rules']})
    answer=Agent(store,Model()).run(t['task_id'],'先算一下，不清楚的问我')
    assert answer['status']=='NEEDS_INPUT'
    assert '1份' not in answer['answer_text'] and '普通品质' not in answer['answer_text'] and '无职业' not in answer['answer_text']
    assert '不承诺' in answer['answer_text'] and '默认值' in answer['answer_text'] and '可核验来源' in answer['answer_text']
    assert '1份' in answer['tool_events'][0]['result']['proposed_question']


def registered_test_image(store,task):
    import io
    from PIL import Image
    from stardew_agent.online_vision import ImageStore
    buf=io.BytesIO();Image.new('RGB',(8,8),'red').save(buf,format='PNG')
    images=ImageStore();upload=images.upload(buf.getvalue(),task['task_id']);region=images.region(upload['image_id'],task['task_id'],[0,0,1,1])
    return store.invalidate(task['task_id'],task['revision'],'test_region',selected_regions=[region]),region


def test_visual_candidates_render_receipt_without_identity_or_calculation(tmp_path,monkeypatch):
    from stardew_agent.task_contract import coverage,current_visual_receipts
    store=TaskStore(tmp_path/'tasks.db');s=Snapshot(allow_candidate=True);t,region=registered_test_image(store,store.create(s.id))
    class Matcher:
        def __init__(self,*a):pass
        def match(self,*a):return {'status':'NEEDS_CONFIRMATION','candidates':[{'entity_id':'entity:Parsnip','name':'Parsnip','distance':.1}],'automatic_identity_confirmation':False}
    monkeypatch.setattr('stardew_agent.agent.VisualMatcher',Matcher)
    class Model:
        def __init__(self):self.round=0
        def call(self,*a,**k):
            self.round+=1
            if self.round==1:return call('set_task_goals',{'goals':[{'id':'visual','kind':'visual_candidates','user_quote':'看看候选','region_id':region['region_id']}]})
            if self.round==2:return call('resolve_visual',{'region_id':region['region_id']})
            return {'status':'OK','content':json.dumps({'answer_text':'肯定是防风草，999个。','status':'ANSWERED'})}
    answer=Agent(store,Model()).run(t['task_id'],'看看候选')
    assert answer['status']=='NEEDS_CONFIRMATION' and answer['goal_coverage']['complete']
    assert '候选' in answer['answer_text'] and '身份尚未确认' in answer['answer_text'] and '999' not in answer['answer_text']
    assert not store.get(t['task_id'])['inputs'].get('confirmed_entities') and not answer['calculation_traces']
    current=store.get(t['task_id']);receipts={r['receipt_id']:r for r in answer['visual_receipts']}
    assert current_visual_receipts(current,receipts)==receipts
    current['goal_spec']['goals'][0]['kind']='identification'
    assert not coverage(current,{}, {},visual_receipts=receipts)['complete']
    current['revision']+=1
    assert not current_visual_receipts(current,receipts)

def test_inventory_identity_cannot_be_invented_from_candidate_or_longer_seed_name(tmp_path):
    from stardew_agent.retrieval import Retriever,unique_identity_mention
    s=Snapshot(allow_candidate=True);store=TaskStore(tmp_path/'tasks.db');t=store.create(s.id);agent=Agent(store,object());aliases=Retriever(s).identity_aliases
    assert not unique_identity_mention('entity:Kale','3个甘蓝种子',aliases)
    assert unique_identity_mention('entity:Kale','甘蓝与3个甘蓝种子',aliases)
    for quote in ('3个普通，无职业','3个普通甘蓝种子'):
        with pytest.raises(ValidationError,match='STATE_ENTITY_NOT_IN_QUOTE|AMBIGUOUS_ENTITY_ALIAS'):
            agent.dispatch('update_task_state',{'fields':{'inventory':{'Kale':{'normal':3}}},'evidence_quote':quote},t['task_id'],s,quote)
    quote='3个普通甘蓝'
    result=agent.dispatch('update_task_state',{'fields':{'inventory':{'Kale':{'normal':3}}},'evidence_quote':quote},t['task_id'],s,quote)
    assert result['inputs']['inventory']['Kale']=={'normal':3}

def test_independent_text_item_can_calculate_with_other_unconfirmed_roi(tmp_path):
    from stardew_agent.task_contract import parameter_binding
    store=TaskStore(tmp_path/'tasks.db');s=Snapshot(allow_candidate=True);t,region=registered_test_image(store,store.create(s.id))
    t=store.begin_turn(t['task_id'],'请看图中候选，另外算3个普通甘蓝的售价，无职业。')
    t=store.update(t['task_id'],t['revision'],{'entity_inputs':{'entity:Kale':{'quantity':3,'quality':'normal'}},'profession':'none'})
    t=store.set_goals(t['task_id'],t['revision'],{'goals':[
        {'id':'visual','kind':'visual_candidates','user_quote':'看图中候选','region_id':region['region_id']},
        {'id':'sale','kind':'calculation','user_quote':'算3个普通甘蓝的售价','entity_id':'entity:Kale','rule_ids':['sale_value']}]})
    result=parameter_binding(t,'sale_value',P,list(P),goal_id='sale')
    assert result['status']=='BOUND' and not t['inputs'].get('confirmed_entities')

def test_shortened_quote_cannot_turn_seed_into_crop_or_seed_question_into_crop_fact(tmp_path):
    s=Snapshot(allow_candidate=True);store=TaskStore(tmp_path/'tasks.db');t=store.create(s.id);agent=Agent(store,object())
    full='甘蓝种子多少钱'
    t=store.begin_turn(t['task_id'],full)
    with pytest.raises(ValidationError,match='AMBIGUOUS_ENTITY_ALIAS'):
        agent.dispatch('update_task_state',{'fields':{'entity_id':'entity:Kale'},'evidence_quote':'甘蓝'},t['task_id'],s,full)
    result=agent.dispatch('set_task_goals',{'goals':[{'id':'price','kind':'knowledge','user_quote':'甘蓝','entity_id':'entity:Kale'}]},t['task_id'],s,full)
    assert result['status']=='GOAL_IDENTITY_NOT_USER_BOUND'
    full='甘蓝与甘蓝种子各多少钱'
    t=store.begin_turn(t['task_id'],full)
    result=agent.dispatch('set_task_goals',{'goals':[{'id':'price','kind':'knowledge','user_quote':'甘蓝','entity_id':'entity:Kale'}]},t['task_id'],s,full)
    assert result['goal_spec']['goals'][0]['entity_id']=='entity:Kale'

@pytest.mark.parametrize('full,quote,quantity',[('30个普通甘蓝','0个普通甘蓝',0),('30个普通甘蓝','3',3),('0.5个甘蓝','5个甘蓝',5)])
def test_excerpt_cannot_split_numeric_tokens(tmp_path,full,quote,quantity):
    s=Snapshot(allow_candidate=True);store=TaskStore(tmp_path/'tasks.db');t=store.begin_turn(store.create(s.id)['task_id'],full)
    with pytest.raises(ValidationError,match='QUOTE'):
        Agent(store,object()).dispatch('update_task_state',{'fields':{'quantity':quantity},'evidence_quote':quote},t['task_id'],s,full)
    with pytest.raises(ValidationError,match='QUOTE'):
        store.update(t['task_id'],t['revision'],{'quantity':quantity},source='user_text_extracted',quote=quote)

@pytest.mark.parametrize('full,quote,quantity',[('30个普通甘蓝','30个普通甘蓝',30),('30个甘蓝，另有3个甜瓜','3个甜瓜',3)])
def test_complete_numeric_tokens_and_independent_mentions_remain_valid(tmp_path,full,quote,quantity):
    store=TaskStore(tmp_path/'tasks.db');t=store.begin_turn(store.create('synthetic')['task_id'],full)
    t=store.update(t['task_id'],t['revision'],{'quantity':quantity},source='user_text_extracted',quote=quote)
    assert t['inputs']['quantity']==quantity

def test_runtime_never_accepts_hidden_or_changed_server_evidence_into_checker():
    from stardew_agent.agent import visible_result_records
    visible={'id':'fact:visible','subject':'entity:Kale','value':6}
    hidden={'id':'fact:hidden','subject':'entity:Calendar','predicate':'watered_growth','value':True}
    result={'facts':[visible,hidden],'model_payload':{'facts':[visible]}}
    accepted,rejected=visible_result_records(result,{})
    assert accepted==[visible] and rejected==[hidden['id']]
    result={'facts':[{**visible,'value':7}],'model_payload':{'facts':[]}}
    accepted,rejected=visible_result_records(result,{visible['id']:visible})
    assert not accepted and rejected==[visible['id']]
    result={'facts':[visible,hidden],'model_payload':{'facts':[hidden]}}
    assert visible_result_records(result,{visible['id']:visible})==([visible,hidden],[])


def test_comparison_schema_feedback_and_new_goal_bundle_invalidation(tmp_path):
    from stardew_agent.agent import GOAL_SCHEMA,RECOVERY_HINTS
    from stardew_agent.evidence import BundleStore
    s=Snapshot(allow_candidate=True);store=TaskStore(tmp_path/'tasks.db');t=store.begin_turn(store.create(s.id)['task_id'],'比较甜瓜的加工价值')
    agent=Agent(store,object(),retrieval_method='B')
    old=agent.dispatch('retrieve_knowledge',{'query':'甜瓜加工','entity_ids':['entity:Melon']},t['task_id'],s,'比较甜瓜的加工价值')
    goal={'id':'compare','kind':'comparison','user_quote':'比较甜瓜的加工价值','entity_id':'entity:Melon','rule_ids':['processing_value'],'product_ids':['entity:Wine']}
    bad=agent.dispatch('set_task_goals',{'goals':[goal]},t['task_id'],s,'比较甜瓜的加工价值')
    assert bad['status']=='GOAL_SCHEMA_ERROR' and bad['error_code']=='COMPARISON_ALTERNATIVES_REQUIRED'
    assert not bad['state_changed'] and store.get(t['task_id'])['revision']==t['revision']
    assert 'calculation' in bad['schema_feedback']['single_processed_vs_raw'] and '2' in bad['schema_feedback']['comparison']
    assert '至少2' in GOAL_SCHEMA['properties']['product_ids']['description']
    goal['product_ids']=['entity:Wine','entity:Jelly']
    good=agent.dispatch('set_task_goals',{'goals':[goal]},t['task_id'],s,'比较甜瓜的加工价值')
    assert good['bundle_policy']['previous_bundles']=='INVALIDATED'
    assert 'retrieve_knowledge' in good['bundle_policy']['before_dependency_fetch_or_execution']
    with pytest.raises(ValidationError,match='STALE_TASK_OR_SNAPSHOT'):
        BundleStore().get(old['bundle_id'],task_id=t['task_id'],revision=good['revision'],snapshot_id=s.id)
    assert 'retrieve_knowledge' in RECOVERY_HINTS['STALE_TASK_OR_SNAPSHOT']
    # One processed alternative versus raw is representable without a fake
    # second product because the calculator already gives raw opportunity cost.
    goal.update(kind='calculation',product_ids=['entity:Wine'])
    assert agent.dispatch('set_task_goals',{'goals':[goal]},t['task_id'],s,'比较甜瓜的加工价值')['revision']==good['revision']+1


def test_knowledge_repair_preserves_user_language_and_drops_unrequested_expansion():
    goals={'growth':{'id':'growth','kind':'explanation','user_quote':'首次成熟总共需要多久？'}}
    evidence={'fact:g':{'id':'fact:g','subject':'entity:Kale','predicate':'growth_days','value':6},
        'evidence:raw':{'id':'evidence:raw','quote':'Stage 1 Stage 2: 1 day 2 days'}}
    class Model:
        def call(self,messages,**kw):
            prompt=messages[0]['content'];packet=json.loads(messages[1]['content'])
            assert 'user message language' in prompt and 'Chinese' in prompt
            assert 'remove unrequested stage sequences' in prompt and 'Raw quote digits do not authorize' in prompt
            assert packet['user_message']=='首次成熟总共需要多久？' and set(packet['allowed_numeric_values'])=={'6','6.0'}
            return {'status':'OK','execution_mode':'synthetic_fixture','content':json.dumps({'knowledge_sections':[{'goal_id':'growth','text':'生长周期为6天。','evidence_refs':['fact:g']}]})}
    sections,report=repair_knowledge_sections(Model(),[{'goal_id':'growth','text':'阶段1再到阶段2。','evidence_refs':['evidence:raw']}],goals,evidence,{},[{'goal_id':'growth','reason':'unsupported numbers'}])
    assert report['accepted'] and sections[0]['text']=='生长周期为6天。'
    assert '1' not in sections[0]['text'] and '2' not in sections[0]['text']


@pytest.mark.parametrize('responses,expected,calls',[
    ([{'status':'OK','parsed':{}},{'status':'OK','parsed':{'verdict':'supported','issues':[]}}],'CHECKED',2),
    ([{'status':'INVALID_JSON','content':'not JSON'},{'status':'OK','parsed':{'verdict':'supported','issues':[]}}],'CHECKED',2),
    ([{'status':'OK','parsed':{}},{'status':'OK','parsed':{}}],'INVALID_CHECK_JSON',2),
    ([{'status':'OK','parsed':{'verdict':'unsupported','issues':[]} }],'CHECKED',1),
    ([{'status':'ERROR','reason':'network'}],'ERROR',1),
    ([{'status':'OK','parsed':{'verdict':'unsupported','issues':'malformed'}},{'status':'OK','parsed':{'verdict':'supported','issues':[]}}],'INVALID_CHECK_JSON',2),
])
def test_grounding_format_retry_is_bounded_same_packet_and_never_auto_passes(responses,expected,calls):
    from stardew_agent.agent import grounding_check
    class Model:
        def __init__(self):self.contexts=[];self.labels=[]
        def structured(self,prompt,context,**kw):
            self.contexts.append(json.loads(json.dumps(context)));self.labels.append(kw['label'])
            return responses[len(self.contexts)-1]
    model=Model();answer={'answer_text':'候选记录售价6g。','claim_evidence_refs':['fact:p']}
    result=grounding_check(model,answer,{'fact:p':{'id':'fact:p','value':6}},{}, {})
    assert result['status']==expected and len(model.contexts)==calls and result['structured_calls']==calls
    assert all(c==model.contexts[0] for c in model.contexts)
    assert result['format_retries']==calls-1 and result['attempts'][0]['response']['status']==responses[0]['status']
    if calls==2:
        assert model.labels[-1]=='v3_answer_grounding_format_recheck'
        assert result['attempts'][0]['packet_hash']==result['attempts'][1]['packet_hash']
    if expected!='CHECKED':assert result['verdict']!='supported'


def test_grounding_format_retry_rejects_goal_set_change():
    from stardew_agent.agent import grounding_check
    class Model:
        def __init__(self):self.calls=0
        def structured(self,*a,**k):
            self.calls+=1
            return {'status':'OK','parsed':{'section_verdicts':[{'goal_id':'wrong','verdict':'supported','issues':[]}]}}
    model=Model();goal={'id':'right','kind':'knowledge','user_quote':'售价'};section={'goal_id':'right','text':'6g','evidence_refs':['fact:p']}
    result=grounding_check(model,{'answer_text':'6g','claim_evidence_refs':['fact:p']},{'fact:p':{'value':6}},{},{},goal_constraints=[{'goal':goal,'section':section}])
    assert model.calls==2 and result['status']=='INVALID_CHECK_JSON' and not result['section_results']


def test_one_format_retry_budget_for_entire_agent_answer(tmp_path):
    s=Snapshot(allow_candidate=True);fact=next(f for f in s.domain['facts'] if f['subject']=='entity:Kale' and f['predicate']=='sell_normal')
    class Model(MixedModel):
        def __init__(self):super().__init__(fact);self.checks=0
        def structured(self,*a,**kw):
            self.checks+=1
            if self.checks==2:return {'status':'OK','execution_mode':'synthetic_fixture','parsed':{'verdict':'unsupported','issues':[{'claim':'fixture','reason':'fixture rejection'}]}}
            return {'status':'OK','execution_mode':'synthetic_fixture','parsed':{}}
    store=TaskStore(tmp_path/'tasks.db');task=store.create(s.id);model=Model()
    answer=Agent(store,model,retrieval_method='B').run(task['task_id'],REQUEST)
    assert answer['status']=='PARTIAL_ANSWER' and not answer['goal_coverage']['complete']
    assert model.checks==3 and answer['budget']['grounding_format_repair_calls']==1
    assert answer['budget']['grounding_calls']==3 and answer['budget']['max_rounds']==12
    assert answer['grounding_checks'][0]['attempts'][0]['validation']['status']=='INVALID_CHECK_JSON'
    assert answer['grounding_checks'][-1]['format_retries']==0


def test_global_negative_format_check_cannot_upgrade_one_section_in_mixed_retry():
    from stardew_agent.agent import grounding_check
    sections=[{'goal_id':g,'text':'6g','evidence_refs':['fact:p']} for g in ('A','B')]
    constraints=[{'goal':{'id':s['goal_id'],'kind':'knowledge','user_quote':'售价'},'section':s} for s in sections]
    class Model:
        def __init__(self):self.calls=0
        def structured(self,*a,**k):
            self.calls+=1
            if self.calls==1:return {'status':'OK','parsed':{'verdict':'unsupported','issues':[{'claim':'A','reason':'support absent'}]}}
            return {'status':'OK','parsed':{'section_verdicts':[
                {'goal_id':'A','verdict':'supported','issues':[]},
                {'goal_id':'B','verdict':'unsupported','issues':[{'claim':'B','reason':'unsupported'}]}]}}
    model=Model();result=grounding_check(model,{'answer_text':'6g','claim_evidence_refs':['fact:p']},{'fact:p':{'value':6}},{},{},goal_constraints=constraints)
    assert model.calls==2 and result['status']=='INVALID_CHECK_JSON' and not result['section_results']
    assert result['reason']=='FORMAT_RECHECK_CANNOT_UPGRADE_NEGATIVE_VERDICT'
    assert result['attempts'][0]['response']['parsed']['verdict']=='unsupported'


class ReceiptOnLastRound:
    """Scripted reasoning with real local tools; never a live quality score."""
    def __init__(self,request,extra_goal=None):self.request=request;self.extra_goal=extra_goal;self.calls=0;self.bundle=None
    def call(self,messages,**kwargs):
        self.calls+=1
        if self.calls==1:
            goals=[{'id':'sale','kind':'calculation','user_quote':self.request,'entity_id':'entity:Kale','rule_ids':['sale_value'],'params':{'quantity':3,'quality':'normal','profession':'none'}}]
            if self.extra_goal:goals.append(self.extra_goal)
            return call('set_task_goals',{'goals':goals})
        if self.calls==2:return call('update_task_state',{'fields':P,'evidence_quote':self.request})
        if self.calls==3:return call('retrieve_knowledge',{'query':'甘蓝普通售价','entity_ids':['entity:Kale']})
        if self.calls==4:
            self.bundle=json.loads(messages[-1]['content'])['bundle_id']
            return call('fetch_dependencies',{'rule_id':'sale_value','bundle_id':self.bundle,'params':P})
        if self.calls==5:
            self.bundle=json.loads(messages[-1]['content'])['bundle_id']
            return call('execute_rule',{'rule_id':'sale_value','bundle_id':self.bundle,'params':P,'goal_id':'sale'})
        raise AssertionError('Exhaustion finalization requested another model call')
    def structured(self,*args,**kwargs):raise AssertionError('Exhaustion finalization must not add a grounding/model call')


@pytest.mark.parametrize('extra_kind',[None,'explanation','calculation'])
def test_last_round_receipt_delivered_with_honest_completion(tmp_path,extra_kind):
    request='算3个普通甘蓝的直接售价，无职业。'
    extra=None
    if extra_kind=='explanation':
        request+='还请解释甘蓝的生长周期。'
        extra={'id':'extra','kind':'explanation','entity_id':'entity:Kale','user_quote':'还请解释甘蓝的生长周期。'}
    elif extra_kind=='calculation':
        request+='还要根据日期计算甘蓝成熟日。'
        extra={'id':'extra','kind':'calculation','entity_id':'entity:Kale','user_quote':'还要根据日期计算甘蓝成熟日。','rule_ids':['growth_timing']}
    store=TaskStore(tmp_path/'tasks.db');task=store.create(Snapshot(allow_candidate=True).id);model=ReceiptOnLastRound(request,extra)
    answer=Agent(store,model,max_rounds=5,retrieval_method='B').run(task['task_id'],request)
    assert answer['status']==('CANDIDATE_ANSWER' if extra_kind is None else 'PARTIAL_ANSWER'),answer
    assert '330g' in answer['answer_text'] and answer['calculation_traces'][0]['outputs']['sales_g']==330
    assert answer['goal_coverage']['complete']==(extra_kind is None)
    assert answer['goal_coverage']['missing_goal_ids']==([] if extra_kind is None else ['extra'])
    assert answer['budget_finalization']['applied'] and answer['budget_finalization']['additional_model_calls']==0
    assert not answer['goal_coverage']['semantic_exhaustiveness_verified'] and not answer['human_approval']
    assert model.calls==answer['budget']['model_agent_calls']==answer['budget']['max_rounds']==5
    assert answer['budget']['grounding_calls']==0 and not answer['answer_repairs']


@pytest.mark.parametrize('mutation,expected',[('cancel','CANCELLED'),('inputs','STATE_CHANGED')])
def test_last_round_cancel_or_edit_wins_over_receipt_delivery(tmp_path,mutation,expected):
    request='算3个普通甘蓝的直接售价，无职业。';store=TaskStore(tmp_path/'tasks.db');task=store.create(Snapshot(allow_candidate=True).id)
    class MutatingAgent(Agent):
        def dispatch(self,name,*args,**kwargs):
            result=super().dispatch(name,*args,**kwargs)
            if name=='execute_rule' and result.get('run_id'):
                current=store.get(task['task_id'])
                if mutation=='cancel':store.cancel(task['task_id'],current['revision'])
                else:store.update(task['task_id'],current['revision'],{'quantity':4})
            return result
    answer=MutatingAgent(store,ReceiptOnLastRound(request),max_rounds=5,retrieval_method='B').run(task['task_id'],request)
    assert answer['status']==expected and not answer['calculation_traces']
    assert not answer['goal_coverage']['complete'] and '330' not in answer['answer_text']
    assert not answer.get('budget_finalization',{}).get('applied')


def test_cancellation_during_deterministic_render_clears_public_receipts(tmp_path,monkeypatch):
    from stardew_agent import answer_rendering
    request='算3个普通甘蓝的直接售价，无职业。';store=TaskStore(tmp_path/'tasks.db');task=store.create(Snapshot(allow_candidate=True).id)
    original=answer_rendering.composite_answer
    def cancelling_render(*args,**kwargs):
        answer=original(*args,**kwargs);current=store.get(task['task_id']);store.cancel(task['task_id'],current['revision']);return answer
    monkeypatch.setattr(answer_rendering,'composite_answer',cancelling_render)
    answer=Agent(store,ReceiptOnLastRound(request),max_rounds=5,retrieval_method='B').run(task['task_id'],request)
    assert answer['status']=='CANCELLED' and not answer['calculation_traces'] and not answer['calculation_trace_refs']
    assert not answer['goal_coverage']['complete'] and not answer['budget_finalization']['applied']
    assert not answer['budget_finalization']['included_run_ids'] and '330' not in answer['answer_text']


def test_exhaustion_receipt_filter_rejects_stale_unsupported_and_unknown_completion(tmp_path,monkeypatch):
    import copy
    from stardew_agent.agent import finalizable_calculation_receipts
    from stardew_agent.task_contract import coverage
    from stardew_agent.rules import rule_fingerprint
    from stardew_agent.answer_rendering import composite_answer
    request='算3个普通甘蓝的直接售价，无职业。';store=TaskStore(tmp_path/'tasks.db');task=store.create(Snapshot(allow_candidate=True).id)
    answer=Agent(store,ReceiptOnLastRound(request),max_rounds=5,retrieval_method='B').run(task['task_id'],request)
    state=store.get(task['task_id']);state['status']='RUNNING';receipt=answer['calculation_traces'][0];rid=receipt['run_id']
    evidence={r['id']:r for e in answer['tool_events'] for key in ('facts','relations','evidence_refs','evidence_inputs') for r in e['result'].get(key,[])}
    events=answer['tool_events'];fingerprints={'sale_value':rule_fingerprint('sale_value')}
    def no_lookup(*args,**kwargs):raise AssertionError('Finalizer attempted hidden graph/bundle IO')
    monkeypatch.setattr('stardew_agent.agent.Snapshot',no_lookup)
    monkeypatch.setattr('stardew_agent.agent.BundleStore.get',no_lookup)
    assert finalizable_calculation_receipts(state,{rid:receipt},evidence,{},events,fingerprints=fingerprints)==({rid:receipt},{})
    for mutate in ('revision','task','snapshot','status','fingerprint','bundle','registration','evidence','provenance','plan'):
        current=copy.deepcopy(state);calc=copy.deepcopy(receipt);visible=copy.deepcopy(evidence)
        if mutate=='revision':calc['task_revision']-=1
        if mutate=='task':calc['task_id']='other-task'
        if mutate=='snapshot':calc['snapshot_id']='other-snapshot'
        if mutate=='status':calc['status']='INCOMPLETE_EVIDENCE'
        if mutate=='fingerprint':calc['rule_fingerprint']='old-code'
        if mutate=='bundle':calc['bundle_id']='bundle:unseen'
        if mutate=='registration':current['results']=[]
        if mutate=='evidence':visible.pop(calc['used_fact_ids'][0])
        if mutate=='provenance':visible.pop(calc['used_evidence_ids'][0])
        if mutate=='plan':calc['plan_context']={'plan_id':'old-plan','task_revision':state['revision'],'snapshot_id':state['snapshot_id']}
        kept,rejected=finalizable_calculation_receipts(current,{rid:calc},visible,{},events,fingerprints=fingerprints)
        assert not kept and rid in rejected,mutate
    unknown=copy.deepcopy(state);unknown['goal_spec']={}
    kept,rejected=finalizable_calculation_receipts(unknown,{rid:receipt},evidence,{},events,fingerprints=fingerprints)
    report=coverage(unknown,kept,evidence,fingerprints=fingerprints)
    assert not rejected and report['status']=='UNSPECIFIED' and not report['complete']
    rendered=composite_answer(kept,{},evidence,[],report,candidate=True)
    assert '330g' in rendered['answer_text'] and '不能判定整题完成' in rendered['answer_text']


@pytest.mark.parametrize('visual_kind',['visual_candidates','identification'])
def test_exhaustion_mixed_visual_and_calculation_delivers_both_without_confirming(tmp_path,monkeypatch,visual_kind):
    request='看看图像候选，另外算3个普通甘蓝的直接售价，无职业。'
    store=TaskStore(tmp_path/'tasks.db');task,region=registered_test_image(store,store.create(Snapshot(allow_candidate=True).id))
    class Matcher:
        def __init__(self,*args):pass
        def match(self,*args):return {'status':'NEEDS_CONFIRMATION','candidates':[{'entity_id':'entity:Parsnip','name':'Parsnip','distance':.1}],'automatic_identity_confirmation':False}
    monkeypatch.setattr('stardew_agent.agent.VisualMatcher',Matcher)
    extra={'id':'visual','kind':visual_kind,'user_quote':'看看图像候选','region_id':region['region_id']}
    class Model(ReceiptOnLastRound):
        def call(self,messages,**kwargs):
            result=super().call(messages,**kwargs)
            if self.calls==3:result['tool_calls'].insert(0,call('resolve_visual',{'region_id':region['region_id']})['tool_calls'][0])
            return result
    model=Model(request,extra)
    answer=Agent(store,model,max_rounds=5,retrieval_method='B').run(task['task_id'],request)
    assert answer['status']==('CANDIDATE_ANSWER' if visual_kind=='visual_candidates' else 'PARTIAL_ANSWER')
    assert '330g' in answer['answer_text'] and '防风草' in answer['answer_text'] and '身份尚未确认' in answer['answer_text']
    assert answer['visual_trace_refs']==[r['receipt_id'] for r in answer['visual_receipts']]
    assert answer['visual_trace_refs'] and not store.get(task['task_id'])['inputs'].get('confirmed_entities')
    assert answer['goal_coverage']['complete']==(visual_kind=='visual_candidates')
    assert answer['budget_finalization']['applied'] and answer['budget']['grounding_calls']==0
    assert model.calls==5 and answer['budget_finalization']['additional_model_calls']==0
