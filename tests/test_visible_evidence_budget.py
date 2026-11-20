"""Budget regressions use frozen sources, not product-accuracy gold or live models."""
import copy
import pytest

from stardew_agent.core import canonical
from stardew_agent.knowledge import Snapshot
from stardew_agent.retrieval import Retriever
from stardew_agent.evidence import BundleStore
from stardew_agent.evidence_payload import BUDGET_DEFINITION_HASH, chars
from stardew_agent.evaluation_protocol import budget_contract_errors, stage_metrics


@pytest.fixture(scope='module')
def snapshot():
    return Snapshot('c704b0819193e793a6f5088b3d2dac57363698cd687bb74e5eb6ae3e8cddf303',allow_candidate=True)


def unpack(snapshot, result):
    return BundleStore().get(result['bundle_id'], task_id='budget-fixture',revision=1,snapshot_id=snapshot.id).data()


@pytest.mark.parametrize('method',['B','BQ','C','D'])
def test_real_c704_full_visible_payload_not_primary_record_count(snapshot, method):
    result=Retriever(snapshot).retrieve('甘蓝适合什么季节种植，首次成熟需要几个有效生长夜晚？请说明依据。',
        entity_ids=['entity:Kale'],method=method,candidate=True,task_id='budget-fixture',revision=1)
    payload=result['model_payload'];body=unpack(snapshot,result);receipt=result['budget_receipt']
    assert chars(payload)<=6000
    assert chars(payload)==receipt['model_visible_evidence_chars']==result['trace']['budget_used']['unicode_chars']
    assert receipt['budget_definition_hash']==BUDGET_DEFINITION_HASH
    ids=lambda data:{r['id'] for key in ('facts','relations') for r in data[key]}
    assert ids(payload)==ids(body)==set(result['trace']['selected_ids'])
    sources={r['id']:r['quote'] for r in body['evidence_refs']}
    assert {r['id']:r['quote'] for r in payload['evidence_refs']}==sources
    assert receipt['full_bundle_unicode_chars']==len(canonical(body))
    assert 'candidate_ids' not in payload['trace'] and 'traversed' not in payload['trace']
    assert not budget_contract_errors({'tool_events':[{'tool':'retrieve_knowledge','result':result}]},6000)


def test_explicit_supplement_delivers_all_new_facts_and_sources_in_batches(snapshot):
    retriever=Retriever(snapshot)
    initial=retriever.retrieve('甘蓝生长',entity_ids=['entity:Kale'],candidate=True,method='B',task_id='budget-fixture',revision=1)
    body=unpack(snapshot,initial)
    seen_records={r['id'] for k in ('facts','relations') for r in body[k]}
    seen_evidence={r['id'] for r in body['evidence_refs']}
    chosen=[r for r in snapshot.domain['facts'] if r['id'] not in seen_records and len(canonical(r['value']))<200][:18]
    selectors=[{'kind':'fact','id':r['id']} for r in chosen]
    missing=selectors;last=initial;total=chars(initial['model_payload']);rounds=0
    from stardew_agent.rules import missing_dependencies
    while missing and rounds<10:
        bundle=BundleStore().get(last['bundle_id'],task_id='budget-fixture',revision=1,snapshot_id=snapshot.id)
        last=retriever.supplement(bundle,missing,candidate=True);payload=last['model_payload'];body=unpack(snapshot,last)
        assert chars(payload)<=6000 and last['status']!='BLOCKED'
        added={r['id'] for k in ('facts','relations') for r in payload[k]}
        new_sources={r['id'] for r in payload['evidence_refs']}
        assert added and not added & seen_records
        assert {r['id'] for k in ('facts','relations') for r in body[k]}==seen_records|added
        assert {r['id'] for r in body['evidence_refs']}==seen_evidence|new_sources
        seen_records|=added;seen_evidence|=new_sources;rounds+=1;total+=chars(payload)
        assert last['budget_receipt']['cumulative_model_visible_evidence_chars']==total
        assert body['initial_retrieval_refs']==[initial['trace']['trace_id']]
        missing=missing_dependencies(body,selectors)
    assert not missing and rounds>=2


def test_single_oversized_record_is_blocked_without_hidden_bundle_addition(snapshot):
    modified=copy.deepcopy(snapshot)
    target=next(r for r in modified.domain['facts'] if r['subject']!='entity:Kale')
    target['value']='synthetic oversize '+('x'*8000)
    modified.records['facts'][target['id']]=target
    retriever=Retriever(modified)
    initial=retriever.retrieve('甘蓝生长',entity_ids=['entity:Kale'],candidate=True,method='B',task_id='budget-fixture',revision=1)
    bundle=BundleStore().get(initial['bundle_id'],task_id='budget-fixture',revision=1,snapshot_id=snapshot.id)
    result=retriever.supplement(bundle,[{'kind':'fact','id':target['id']}],candidate=True)
    assert result['status']=='BLOCKED' and result['model_payload']['supplement_status']=='BLOCKED'
    assert result['reason']=='SUPPLEMENT_EVIDENCE_BUDGET_NO_PROGRESS'
    assert target['id'] not in {r['id'] for r in unpack(snapshot,result)['facts']}
    assert chars(result['model_payload'])<=6000


def test_all_tool_messages_contribute_to_character_proxy():
    events=[{'tool':'get_evidence','result':{'record':{'id':'f','value':'source text'}}},
            {'tool':'discover_rules','result':{'rules':[{'id':'r'}]}},
            {'tool':'execute_rule','result':{'outputs':{'sales_g':330}}},
            {'tool':'retrieve_knowledge','result':{'model_payload':{'facts':[]},'server_only':'not sent'}}]
    metrics=stage_metrics({'tool_events':events})
    assert metrics['cost']['cumulative_model_visible_chars']==sum(chars(e['result'].get('model_payload',e['result'])) for e in events)


def test_inconsistent_receipt_and_hidden_initial_fact_are_rejected():
    result={'facts':[{'id':'hidden'}],'relations':[],'trace':{'selected_ids':['hidden']},
        'model_payload':{'facts':[],'relations':[]},
        'budget_receipt':{'model_visible_evidence_chars':1,'budget_definition_hash':BUDGET_DEFINITION_HASH}}
    errors=budget_contract_errors({'tool_events':[{'tool':'retrieve_knowledge','result':result}]},6000)
    assert '0:VISIBLE_CHARACTER_RECEIPT_MISMATCH' in errors
    assert '0:HIDDEN_OR_MISMATCHED_INITIAL_RECORDS' in errors

@pytest.mark.parametrize('tool_name',['fetch_dependencies','fetch_fact_dependencies'])
def test_supplement_receipt_closure_and_visible_budget_are_audited(snapshot,tool_name):
    retriever=Retriever(snapshot)
    first=retriever.retrieve('甘蓝生长',entity_ids=['entity:Kale'],method='B',candidate=True,task_id='budget-fixture',revision=1)
    bundle=BundleStore().get(first['bundle_id'],task_id='budget-fixture',revision=1,snapshot_id=snapshot.id)
    target=next(r for r in snapshot.domain['facts'] if r['subject']=='entity:Calendar' and r['predicate']=='watered_growth')
    second=retriever.supplement(bundle,[{'kind':'fact','id':target['id']}],candidate=True)
    events=[{'tool':'retrieve_knowledge','result':first},{'tool':tool_name,'result':second}]
    assert not budget_contract_errors({'tool_events':events},6000)
    assert stage_metrics({'tool_events':events})['supplementation']['rounds']==1
    mutated=copy.deepcopy(events);mutated[1]['result']['model_payload']['extra']='x'*6001
    errors=budget_contract_errors({'tool_events':mutated},6000)
    assert '1:SUPPLEMENT_VISIBLE_BUDGET_EXCEEDED' in errors and '1:VISIBLE_CHARACTER_RECEIPT_MISMATCH' in errors
    mutated=copy.deepcopy(events);mutated[1]['result']['model_payload']['facts']=[]
    assert '1:HIDDEN_OR_MISMATCHED_SUPPLEMENT_RECORDS' in budget_contract_errors({'tool_events':mutated},6000)
    mutated=copy.deepcopy(events);mutated[1]['result']['trace']['parent_bundle_id']='unseen'
    assert '1:UNSEEN_SUPPLEMENT_PARENT' in budget_contract_errors({'tool_events':mutated},6000)
    mutated=copy.deepcopy(events);mutated[1]['result']['facts'][0]['value']='server-only altered value'
    assert '1:VISIBLE_CONTENT_MISMATCH:seen_records' in budget_contract_errors({'tool_events':mutated},6000)


def test_fact_unit_supplement_definitions_count_in_actual_payload(snapshot):
    from stardew_agent.capabilities import fact_unit_dependencies
    retriever=Retriever(snapshot)
    first=retriever.retrieve('甘蓝生长周期',entity_ids=['entity:Kale'],method='B',candidate=True,task_id='budget-fixture',revision=1)
    bundle=BundleStore().get(first['bundle_id'],task_id='budget-fixture',revision=1,snapshot_id=snapshot.id)
    fact=next(r for r in bundle.data()['facts'] if r['unit']=='growth_nights')
    contract=fact_unit_dependencies(bundle.data(),[fact['id']])
    second=retriever.supplement(bundle,contract['selectors'],candidate=True,payload_context={'unit_definitions':contract['unit_definitions']})
    assert second['unit_definitions']==second['model_payload']['unit_definitions']
    assert chars(second['model_payload'])==second['budget_receipt']['model_visible_evidence_chars']<=6000
    assert any(r['subject']=='entity:Calendar' and r['predicate']=='watered_growth' for r in second['facts'])
    assert not budget_contract_errors({'tool_events':[{'tool':'retrieve_knowledge','result':first},{'tool':'fetch_fact_dependencies','result':second}]},6000)
