"""Trusted fixture interventions test causal use, not extraction accuracy."""
import copy,hmac
import pytest
from stardew_agent.core import *
from stardew_agent.evidence import VerifiedBundle,secret
from stardew_agent.knowledge import Snapshot
from stardew_agent.calculations import execute
from test_runtime import prepared

def signed_fixture(body):
    # A server-authorized synthetic intervention. Never a production issuance path.
    encoded=canonical(body);return VerifiedBundle(encoded,hmac.new(secret(),encoded.encode(),'sha256').hexdigest())

def test_related_fact_changes_output_and_unrelated_does_not():
    s=Snapshot(allow_candidate=True);p={'entity_id':'entity:Kale','quantity':2,'quality':'normal','profession':'none'}
    b=prepared(s,'sale_value',p);original=execute('sale_value',b,p)['outputs']['sales_g'];assert original==220
    body=b.data();fact=next(f for f in body['facts'] if f['subject']=='entity:Kale' and f['predicate']=='sell_normal');fact['value']=111
    assert execute('sale_value',signed_fixture(body),p)['outputs']['sales_g']==222
    body=b.data();fact=next(f for f in body['facts'] if f['subject']=='entity:Kale' and f['predicate']=='sell_normal')
    irrelevant={**copy.deepcopy(fact),'id':'fact:synthetic_irrelevant','predicate':'synthetic_unrelated','value':9999};body['facts'].append(irrelevant)
    assert execute('sale_value',signed_fixture(body),p)['outputs']['sales_g']==original

def test_unique_source_deletion_rejects_even_signed_inconsistent_bundle():
    s=Snapshot(allow_candidate=True);p={'entity_id':'entity:Kale','quantity':2,'quality':'normal','profession':'none'};body=prepared(s,'sale_value',p).data()
    body['evidence_refs']=[]
    with pytest.raises(ValidationError,match='SOURCE_MISSING'):execute('sale_value',signed_fixture(body),p)

def test_redundant_source_can_be_removed_when_another_valid_source_remains():
    s=Snapshot(allow_candidate=True);p={'entity_id':'entity:Kale','quantity':2,'quality':'normal','profession':'none'};body=prepared(s,'sale_value',p).data()
    fact=next(f for f in body['facts'] if f['subject']=='entity:Kale' and f['predicate']=='sell_normal');ev=next(e for e in body['evidence_refs'] if e['id']==fact['evidence_ids'][0])
    alternate={**copy.deepcopy(ev),'id':'evidence:synthetic_redundant_copy'};body['evidence_refs'].append(alternate);fact['evidence_ids'].append(alternate['id'])
    assert execute('sale_value',signed_fixture(body),p)['outputs']['sales_g']==220
    fact['evidence_ids'].remove(alternate['id']);body['evidence_refs'].remove(alternate)
    assert execute('sale_value',signed_fixture(body),p)['outputs']['sales_g']==220

def test_reversed_critical_relation_does_not_satisfy_dependency():
    s=Snapshot(allow_candidate=True);p={'entity_id':'entity:Parsnip_Seeds','day':23,'season':'Spring','watered':True,'acceleration':'none'};body=prepared(s,'growth_timing',p).data()
    for r in body['relations']:
        if r['predicate']=='GROWS_INTO':r['subject'],r['object']=r['object'],r['subject']
    assert execute('growth_timing',signed_fixture(body),p)['status']=='INCOMPLETE_EVIDENCE'
