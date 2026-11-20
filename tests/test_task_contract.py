"""Synthetic protocol regressions, excluded from live/held-out quality scores."""
import copy
import pytest
from stardew_agent.core import ValidationError
from stardew_agent.state import TaskStore
from stardew_agent.task_contract import normalize_goals,parameter_binding,matching_goals,bind_plan,coverage

REQUEST='解释甜瓜，并比较3个普通甜瓜做果酒和果酱的价值；无职业。'
PARAMS={'entity_id':'entity:Melon','quantity':3,'quality':'normal','profession':'none'}
GOALS=[{'id':'explain','kind':'explanation','user_quote':'解释甜瓜','entity_id':'entity:Melon','predicates':['category']},
       {'id':'compare','kind':'comparison','user_quote':'比较3个普通甜瓜做果酒和果酱的价值','entity_id':'entity:Melon',
        'rule_ids':['processing_value'],'product_ids':['entity:Wine','entity:Jelly'],'params':{'quantity':3,'quality':'normal','profession':'none'}}]

def task_with_goals(tmp_path,goals=None):
    store=TaskStore(tmp_path/'tasks.db');task=store.create('snapshot:test')
    task=store.begin_turn(task['task_id'],REQUEST)
    task=store.update(task['task_id'],task['revision'],{**PARAMS,'product_id':'entity:Wine'})
    task=store.set_goals(task['task_id'],task['revision'],{'goals':goals or GOALS})
    return store,task

def calc(task,product='Wine',**changes):
    out={'run_id':'calc:'+product,'rule_id':'processing_value','rule_fingerprint':'current','task_revision':task['revision'],
         'snapshot_id':task['snapshot_id'],'user_inputs':{**PARAMS,'product_id':'entity:'+product},'outputs':{},'status':'CANDIDATE_RESULT_NOT_RELEASED'}
    out.update(changes);return out

def test_model_cannot_submit_completion_or_unanchored_goals(tmp_path):
    _,task=task_with_goals(tmp_path)
    with pytest.raises(ValidationError,match='FIELDS'):normalize_goals({'goals':[{**GOALS[0],'status':'SATISFIED'}]},task)
    with pytest.raises(ValidationError,match='QUOTE'):normalize_goals({'goals':[{**GOALS[0],'user_quote':'不存在的用户要求'}]},task)

def test_missing_explanation_or_comparison_alternative_never_complete(tmp_path):
    _,task=task_with_goals(tmp_path);a=calc(task);b=calc(task,'Jelly');task['results']=[a['run_id'],b['run_id']]
    evidence={'fact:category':{'subject':'entity:Melon','predicate':'category','value':'fruit'}}
    section={'goal_id':'explain','text':'甜瓜属于水果。','evidence_refs':['fact:category']}
    assert coverage(task,{a['run_id']:a},evidence,[section])['missing_goal_ids']==['compare']
    assert coverage(task,{a['run_id']:a,b['run_id']:b},evidence)['missing_goal_ids']==['explain']
    report=coverage(task,{a['run_id']:a,b['run_id']:b},evidence,[section])
    assert report['complete'] and not report['independently_verified'] and not report['semantic_exhaustiveness_verified']

@pytest.mark.parametrize('field,value',[('quantity',4),('quality','gold'),('entity_id','entity:Kale')])
def test_wrong_goal_operands_rejected(tmp_path,field,value):
    _,task=task_with_goals(tmp_path)
    params={**PARAMS,'product_id':'entity:Wine',field:value}
    assert parameter_binding(task,'processing_value',params,list(params))['status']=='GOAL_PARAMETER_MISMATCH'

def test_goal_proposal_cannot_override_recorded_inputs_or_invent_source(tmp_path):
    _,task=task_with_goals(tmp_path)
    task['goal_spec']['goals'][1]['params']['quantity']=4
    params={**PARAMS,'quantity':4,'product_id':'entity:Wine'}
    assert parameter_binding(task,'processing_value',params,list(params))['status']=='INPUT_CONFLICT'
    task['goal_spec']['goals'][1]['params']['quantity']=3;task['input_sources'].pop('quality')
    params['quantity']=3
    assert parameter_binding(task,'processing_value',params,list(params))['missing_inputs']==['quality']

@pytest.mark.parametrize('source',['global','roi'])
def test_confirmed_identity_cannot_be_replaced_by_goal_proposal(tmp_path,source):
    _,task=task_with_goals(tmp_path);params={**PARAMS,'product_id':'entity:Wine'}
    if source=='global':task['inputs']['entity_id']='entity:Kale'
    else:
        task['inputs'].pop('entity_id');task['inputs']['confirmed_entities']={'roi:one':{'entity_id':'entity:Kale','quantity':3,'quality':'normal'}}
        task['input_sources']['confirmed_entities']={'source':'user_ui','human_confirmation':True};task['selected_regions']=[{'region_id':'roi:one'}]
    assert parameter_binding(task,'processing_value',params,list(params))['status']=='INPUT_CONFLICT'
    task['inputs']['entity_inputs']={'entity:Melon':{'quantity':3,'quality':'normal'}}
    task['input_sources']['entity_inputs']={'source':'user_ui'}
    assert parameter_binding(task,'processing_value',params,list(params))['status']=='BOUND'

@pytest.mark.parametrize('change',[{'task_revision':999},{'snapshot_id':'old'},{'rule_fingerprint':'old'}])
def test_old_revision_snapshot_and_rule_never_satisfy(tmp_path,change):
    _,task=task_with_goals(tmp_path);a=calc(task);b=calc(task,'Jelly',**change);task['results']=[a['run_id'],b['run_id']]
    assert 'compare' in coverage(task,{a['run_id']:a,b['run_id']:b},{},fingerprints={'processing_value':'current'})['missing_goal_ids']

def remaining_task(tmp_path):
    goals=[{'id':'remaining','kind':'calculation','user_quote':'3个普通甜瓜','entity_id':'entity:Melon','rule_ids':['sale_value'],'inventory_scope':'remaining'}]
    _,task=task_with_goals(tmp_path,goals)
    task['inventory_plan_copy']={'status':'FEASIBLE','plan_id':'plan:one','reservation_run_id':'calc:reserve','task_revision':task['revision'],
        'snapshot_id':task['snapshot_id'],'options':[{'remaining':{'Melon':{'normal':3}},'reserved':{}}]}
    return task

def test_plan_identity_and_missing_remaining_item_fail_closed(tmp_path):
    task=remaining_task(tmp_path);goals=task['goal_spec']['goals']
    assert bind_plan(task,'sale_value',PARAMS,goals,'plan:other')['status']=='INVENTORY_PLAN_ID_MISMATCH'
    assert bind_plan(task,'sale_value',{**PARAMS,'entity_id':'entity:Kale'},goals,'plan:one')['status']=='INVENTORY_ITEM_NOT_IN_PLAN'
    assert bind_plan(task,'sale_value',{**PARAMS,'quantity':4},goals,'plan:one')['status']=='INVENTORY_PLAN_CONFLICT'
    assert bind_plan(task,'sale_value',PARAMS,goals,'plan:one')['reservation_run_id']=='calc:reserve'

def test_comparison_cannot_mix_reservation_plans(tmp_path):
    _,task=task_with_goals(tmp_path);a=calc(task);b=calc(task,'Jelly')
    a['plan_context']={'plan_id':'plan:a'};b['plan_context']={'plan_id':'plan:b'};task['results']=[a['run_id'],b['run_id']]
    assert 'compare' in coverage(task,{a['run_id']:a,b['run_id']:b},{})['missing_goal_ids']

@pytest.mark.parametrize('mutation',['input','roi','goal','cancel','turn'])
def test_every_dependency_change_invalidates_answer_and_plan(tmp_path,mutation):
    store,t=task_with_goals(tmp_path);tid=t['task_id'];rev=t['revision']
    store.save_runtime(tid,rev,results=['calc:old'],answer={'answer_text':'old'},last_bundle_id='bundle:old',inventory_plan_copy={'plan_id':'old'})
    if mutation=='input':new=store.update(tid,rev,{'quantity':4})
    elif mutation=='roi':new=store.invalidate(tid,rev,'regions_changed',selected_regions=[])
    elif mutation=='goal':new=store.set_goals(tid,rev,{'goals':GOALS})
    elif mutation=='cancel':new=store.cancel(tid,rev)
    else:new=store.begin_turn(tid,'改成4个。')
    assert new['revision']==rev+1 and not new['results'] and not new['inventory_plan_copy']
    assert 'answer' not in new and 'last_bundle_id' not in new and 'calc:old' in new['stale_result_ids']
    with pytest.raises(ValidationError,match='STALE'):store.save_runtime(tid,rev,answer={'answer_text':'stale'})

def test_cancel_recovery_keeps_inputs_and_old_turn_for_goal_reanchoring(tmp_path):
    store,t=task_with_goals(tmp_path);oldturn=t['current_turn_id'];store.cancel(t['task_id'],t['revision'])
    t=store.begin_turn(t['task_id'],'继续，数量仍为3。')
    assert t['inputs']['quantity']==3 and t['goal_spec']=={} and t['previous_goal_spec']['goals']
    t=store.set_goals(t['task_id'],t['revision'],{'goals':[{**g,'source_turn_id':oldturn} for g in GOALS]})
    assert t['goal_spec']['goals'][0]['source_turn_id']==oldturn and not coverage(t,{}, {})['complete']

def test_quoted_numeric_extraction_rejects_unmentioned_quantity(tmp_path):
    store,t=task_with_goals(tmp_path)
    with pytest.raises(ValidationError,match='NUMBER_NOT_IN_QUOTE'):
        store.update(t['task_id'],t['revision'],{'quantity':30},source='user_text_extracted',quote='3个')
    with pytest.raises(ValidationError,match='NUMBER_NOT_IN_QUOTE'):
        store.update(t['task_id'],t['revision'],{'inventory':{'Melon':{'gold':30}}},source='user_text_extracted',quote='3个')
    with pytest.raises(ValidationError,match='NUMBER_NOT_IN_QUOTE'):
        store.update(t['task_id'],t['revision'],{'entity_inputs':{'entity:Melon':{'quantity':30}}},source='user_text_extracted',quote='3个')

@pytest.mark.parametrize('fields',[{'season':'Spring'},{'watered':True},{'acceleration':'none'}])
def test_retrieved_conditions_cannot_be_saved_as_user_observation(tmp_path,fields):
    store,t=task_with_goals(tmp_path)
    t=store.begin_turn(t['task_id'],'解释它的生长季节和首次成熟天数')
    with pytest.raises(ValidationError,match='VALUE_NOT_IN_QUOTE'):
        store.update(t['task_id'],t['revision'],fields,source='user_text_extracted',quote='解释它的生长季节和首次成熟天数')

def test_model_cannot_write_human_confirmation_or_region_paths(tmp_path):
    store,t=task_with_goals(tmp_path)
    with pytest.raises(ValidationError,match='HUMAN_CONFIRMATION_REQUIRED'):
        store.update(t['task_id'],t['revision'],{'confirmed_entities':{}},source='user_text_extracted',quote=REQUEST)
    for source in ('user_ui','user_text_extracted'):
        with pytest.raises(ValidationError,match='REGIONS_REQUIRE_REGISTERED_IMAGE_API'):
            store.update(t['task_id'],t['revision'],{'selected_regions':[{'region_id':'fake','path':'secret'}]},source=source,quote=REQUEST)
    with pytest.raises(ValidationError,match='CONFIRMATION_REGION_REQUIRED'):
        store.update(t['task_id'],t['revision'],{'confirmed_entities':{'missing':{'entity_id':'entity:Melon'}}})

def test_identification_requires_registered_pixels_and_human_origin(tmp_path):
    import io
    from PIL import Image
    from stardew_agent.online_vision import ImageStore
    store,t=task_with_goals(tmp_path);buffer=io.BytesIO();Image.new('RGB',(8,8),'red').save(buffer,format='PNG')
    images=ImageStore();upload=images.upload(buffer.getvalue(),t['task_id']);region=images.region(upload['image_id'],t['task_id'],[0,0,1,1])
    t=store.invalidate(t['task_id'],t['revision'],'regions_changed',selected_regions=[region])
    goals=[{'id':'identify','kind':'identification','user_quote':'解释甜瓜','entity_id':'entity:Melon','region_id':region['region_id']}]
    t=store.set_goals(t['task_id'],t['revision'],{'goals':goals})
    t=store.update(t['task_id'],t['revision'],{'confirmed_entities':{region['region_id']:{'entity_id':'entity:Melon'}}},source='user_ui')
    assert coverage(t,{}, {})['complete']
    bad=copy.deepcopy(t);bad['input_sources']['confirmed_entities']={'source':'user_text_extracted','human_confirmation':True}
    assert not coverage(bad,{}, {})['complete']
    bad=copy.deepcopy(t);bad['selected_regions'][0]['path']='.env'
    assert not coverage(bad,{}, {})['complete']
    bad=copy.deepcopy(t);bad['inputs']['confirmed_entities'][region['region_id']]='entity:Melon'
    assert not coverage(bad,{}, {})['complete']

def test_model_goal_identity_is_not_a_user_identity_source(tmp_path):
    store=TaskStore(tmp_path/'tasks.db');t=store.create('snapshot:test')
    t=store.begin_turn(t['task_id'],'算3个普通，无职业。')
    t=store.update(t['task_id'],t['revision'],{'quantity':3,'quality':'normal','profession':'none'})
    t=store.set_goals(t['task_id'],t['revision'],{'goals':[{'id':'sale','kind':'calculation','user_quote':'算3个普通，无职业。','entity_id':'entity:Kale','rule_ids':['sale_value']}]})
    params={'entity_id':'entity:Kale','quantity':3,'quality':'normal','profession':'none'}
    result=parameter_binding(t,'sale_value',params,list(params),identity_aliases={'entity:Kale':['甘蓝']})
    assert result['status']=='NEEDS_INPUT' and result['missing_inputs']==['entity_id']
    t['goal_spec']['goals'][0]['region_id']='user_region:unconfirmed'
    result=parameter_binding(t,'sale_value',params,list(params),identity_aliases={'entity:Kale':['甘蓝']})
    assert result['status']=='NEEDS_CONFIRMATION'


def test_text_identity_fallback_requires_actual_original_anchor_and_unique_alias(tmp_path):
    store=TaskStore(tmp_path/'tasks.db');t=store.create('snapshot:test')
    t=store.begin_turn(t['task_id'],'3个普通甘蓝，无职业')
    t=store.update(t['task_id'],t['revision'],{'quantity':3,'quality':'normal','profession':'none'})
    t=store.set_goals(t['task_id'],t['revision'],{'goals':[{'id':'sale','kind':'calculation','user_quote':'3个普通甘蓝，无职业','entity_id':'entity:Kale','rule_ids':['sale_value']}]})
    p={'entity_id':'entity:Kale','quantity':3,'quality':'normal','profession':'none'}
    aliases={'entity:Kale':['甘蓝']}
    result=parameter_binding(t,'sale_value',p,list(p),identity_aliases=aliases,alias_catalog_sha256='fixture-hash')
    assert result['status']=='BOUND' and result['parameter_sources']['entity_id']['source']=='user_text_identity_match'
    aliases['entity:Other']=['甘蓝']
    assert parameter_binding(t,'sale_value',p,list(p),identity_aliases=aliases)['status']=='NEEDS_INPUT'

def open_processing_task(tmp_path,request='3个普通甜瓜怎么加工价值更高，无职业？'):
    store=TaskStore(tmp_path/'tasks.db');t=store.begin_turn(store.create('snapshot:test')['task_id'],request)
    t=store.update(t['task_id'],t['revision'],PARAMS)
    t=store.set_goals(t['task_id'],t['revision'],{'goals':[{'id':'processing','kind':'comparison','user_quote':request,'entity_id':'entity:Melon','rule_ids':['processing_value'],'product_ids':['entity:Wine','entity:Jelly']}]})
    body={'bundle_id':'bundle:test','task_id':t['task_id'],'task_revision':t['revision'],'snapshot_id':t['snapshot_id'],
        'relations':[{'id':'relation:'+p,'subject':'entity:Melon','predicate':'CAN_PROCESS','object':'entity:'+p,'evidence_ids':['evidence:'+p]} for p in ('Wine','Jelly')]}
    return t,body

@pytest.mark.parametrize('product',['Wine','Jelly'])
def test_open_comparison_product_can_come_from_explicit_current_graph(tmp_path,product):
    t,body=open_processing_task(tmp_path);params={**PARAMS,'product_id':'entity:'+product}
    result=parameter_binding(t,'processing_value',params,list(params),evidence_body=body,identity_aliases={'entity:Wine':['果酒'],'entity:Jelly':['果酱']})
    assert result['status']=='BOUND'
    assert result['parameter_sources']['product_id']['source']=='explicit_bundle_processing_relation'
    assert result['parameter_sources']['product_id']['relation_ids']==['relation:'+product]

@pytest.mark.parametrize('mutation',['missing','wrong_subject','stale','snapshot','explicit_other','named_other','unknown_condition'])
def test_product_graph_source_cannot_be_invented_stale_or_override_selection(tmp_path,mutation):
    t,body=open_processing_task(tmp_path,'3个普通甜瓜做果酱，无职业' if mutation=='named_other' else '3个普通甜瓜怎么加工价值更高，无职业？')
    if mutation=='missing':body['relations']=[]
    if mutation=='wrong_subject':body['relations'][0]['subject']='entity:Kale'
    if mutation=='stale':body['task_revision']-=1
    if mutation=='snapshot':body['snapshot_id']='other'
    if mutation=='explicit_other':t['inputs']['product_id']='entity:Jelly';t['input_sources']['product_id']={'source':'user_ui'}
    if mutation=='unknown_condition':body['relations'][0]['conditions']={'unprovided':'required'}
    params={**PARAMS,'product_id':'entity:Wine'}
    assert parameter_binding(t,'processing_value',params,list(params),evidence_body=body,identity_aliases={'entity:Wine':['果酒'],'entity:Jelly':['果酱']})['status']!='BOUND'


def test_partial_processing_bundle_cannot_erase_explicit_other_product(tmp_path):
    t,body=open_processing_task(tmp_path,'3个普通甜瓜做果酱，无职业')
    body['relations']=[body['relations'][0]]  # Only Wine visible, Jelly relation absent.
    t['goal_spec']['goals'][0]['product_ids']=['entity:Wine']  # Even a mistaken model goal cannot erase it.
    t['goal_spec']['goals'][0]['kind']='calculation'
    params={**PARAMS,'product_id':'entity:Wine'}
    aliases={'entity:Melon':['甜瓜'],'entity:Wine':['果酒'],'entity:Jelly':['果酱']}
    result=parameter_binding(t,'processing_value',params,list(params),evidence_body=body,identity_aliases=aliases,
        product_identity_ids={'entity:Wine','entity:Jelly'})
    assert result['status']=='NEEDS_INPUT' and 'product_id' in result['missing_inputs']
    # Omitting the optional typed metadata also fails closed on all names.
    assert parameter_binding(t,'processing_value',params,list(params),evidence_body=body,identity_aliases=aliases)['status']=='NEEDS_INPUT'


def test_complete_product_identity_catalog_only_restricts_never_supplies_relations(tmp_path):
    t,body=open_processing_task(tmp_path);body['relations']=[]
    params={**PARAMS,'product_id':'entity:Wine'}
    result=parameter_binding(t,'processing_value',params,list(params),evidence_body=body,
        identity_aliases={'entity:Wine':['果酒'],'entity:Jelly':['果酱']},product_identity_ids={'entity:Wine','entity:Jelly'})
    assert result['status']=='NEEDS_INPUT'
