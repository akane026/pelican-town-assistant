"""Counterfactual evidence must change eligibility, not only the numeric result."""
import pytest
from stardew_agent.calculations import execute
from stardew_agent.core import ValidationError
from stardew_agent.rules import rule_fingerprint
from stardew_agent.knowledge import Snapshot
from test_runtime import prepared
from test_evidence_interventions import signed_fixture

@pytest.mark.parametrize('conditions',[
    {'profession':'tiller','quality':'normal'},
    {'profession':'none','quality':'gold'},
    {'festival_only':True},
    ['only during an unmodelled event'],
])
def test_inapplicable_price_cannot_satisfy_rule(conditions):
    snapshot=Snapshot(allow_candidate=True)
    params={'entity_id':'entity:Kale','quantity':2,'quality':'normal','profession':'none'}
    body=prepared(snapshot,'sale_value',params).data()
    for fact in body['facts']:
        if fact['subject']=='entity:Kale' and fact['predicate']=='sell_normal':fact['conditions']=conditions
    result=execute('sale_value',signed_fixture(body),params)
    assert result['status']=='INCOMPLETE_EVIDENCE'
    assert 'outputs' not in result

def test_receipt_pins_actual_implementation_and_image_content():
    snapshot=Snapshot(allow_candidate=True)
    params={'entity_id':'entity:Kale','quantity':2,'quality':'normal','profession':'none'}
    bundle=prepared(snapshot,'sale_value',params)
    assert execute('sale_value',bundle,params)['rule_fingerprint']==rule_fingerprint('sale_value')
    body=bundle.data()
    # Explicit image-integrity fixture, separate from bounded text-query output:
    # optional image provenance need not fit every 6000-character retrieval.
    from stardew_agent.evidence import BundleStore
    bundle=BundleStore().create(snapshot,[r['id'] for r in body['facts']],[r['id'] for r in body['relations']],
        ['entity:Kale'],task_id='synthetic-image-integrity',revision=1,trace={'trace_id':'fixture:explicit-image'},candidate=True)
    body=bundle.data()
    assert body['assets'], 'The explicitly constructed image-integrity fixture must carry image evidence.'
    body['assets'][0]['sha256']='0'*64
    with pytest.raises(ValidationError,match='BUNDLE_IMAGE_CHANGED'):
        execute('sale_value',signed_fixture(body),params)

def test_wrong_stage_edge_is_not_substitute_for_selected_stage():
    snapshot=Snapshot(allow_candidate=True)
    params={'entity_id':'entity:Parsnip','stage':3,'watered':True,'acceleration':'none'}
    body=prepared(snapshot,'stage_remaining',params).data()
    body['relations']=[r for r in body['relations'] if not (r['predicate']=='HAS_STAGE' and r.get('conditions',{}).get('ordinal')==3)]
    assert execute('stage_remaining',signed_fixture(body),params)['status']=='INCOMPLETE_EVIDENCE'

def test_seed_edge_must_point_to_the_actual_crop():
    snapshot=Snapshot(allow_candidate=True)
    params={'entity_id':'entity:Parsnip_Seeds','day':23,'season':'Spring','watered':True,'acceleration':'none'}
    body=prepared(snapshot,'growth_timing',params).data()
    for relation in body['relations']:
        if relation['subject']=='entity:Parsnip_Seeds' and relation['predicate']=='GROWS_INTO':relation['object']='entity:Kale'
    assert execute('growth_timing',signed_fixture(body),params)['status']=='INCOMPLETE_EVIDENCE'

def test_inventory_display_title_is_equivalent_to_canonical_wiki_title():
    snapshot=Snapshot(allow_candidate=True)
    params={'entity_id':'entity:Spring_Crops_Bundle','inventory':{'Parsnip':{'normal':6},'Green Bean':{'normal':1},'Cauliflower':{'normal':1},'Potato':{'normal':1}},'completed':[]}
    result=execute('bundle_reserve',prepared(snapshot,'bundle_reserve',params),params)
    assert result['outputs']['status']=='FEASIBLE'
    assert result['outputs']['options'][0]['remaining']['Parsnip']['normal']==5

def test_rule_approval_fingerprint_includes_imported_arithmetic(monkeypatch):
    import stardew_agent.rules as rules
    old=rules.rule_fingerprint('processing_value');real_hash=rules.file_hash
    monkeypatch.setattr(rules,'file_hash',lambda p:'changed-helper' if str(p).endswith('verification/calculators.py') else real_hash(p))
    with pytest.raises(ValidationError,match='IMPLEMENTATION_CHANGED_RESTART_REQUIRED'):
        rules.rule_fingerprint('processing_value')
