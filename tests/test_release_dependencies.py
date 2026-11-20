"""Synthetic approvals are isolated evaluator fixtures, never production decisions."""
from stardew_agent.capabilities import assess_capabilities, audit_release_dependencies


def graph():
    return {'facts':[{'id':'fact:base','subject':'entity:A','predicate':'sell_normal','unit':'g','conditions':{},'review_status':'candidate'},
                     {'id':'fact:formula','subject':'entity:B','predicate':'value_formula','review_status':'candidate'}],
            'relations':[{'id':'relation:derived','method':'source_grounded_category_join','support_fact_ids':['fact:base','fact:formula'],'review_status':'candidate'}]}


def test_transitive_approval_and_missing_base_are_required():
    g=graph();ids={'relation:derived','fact:base'}
    assert audit_release_dependencies(g,ids)['status']=='BLOCKED'
    ids.add('fact:formula');assert audit_release_dependencies(g,ids)['status']=='PASS'
    g['facts'].pop();assert audit_release_dependencies(g,ids)['status']=='BLOCKED'


def test_cycles_cannot_self_justify_even_with_approval():
    g=graph();g['facts'][0]['depends_on']=['relation:derived']
    report=audit_release_dependencies(g,{'relation:derived','fact:base','fact:formula'})
    assert report['status']=='BLOCKED' and report['records'][0]['status']=='INVALID_DEPENDENCY'


def test_or_unreviewed_branch_does_not_block_approved_alternative():
    g=graph();result=assess_capabilities(g,[{'id':'alternatives','dependencies':{'any':[{'record':'relation:derived'},{'record':'fact:base'}]}}],approvals={'fact:base'})
    row=result['capabilities'][0]
    assert row['status']=='AVAILABLE' and row['selected_branch']==1
    assert row['children'][0]['status']=='PENDING_REVIEW'


def test_missing_input_and_pending_review_are_separate_and_fingerprint_bound():
    capability={'id':'sale','dependencies':{'all':[{'input':'quantity'},{'record':'fact:base'},{'rule':{'id':'sale','fingerprint':'v2'}}]}}
    report=assess_capabilities(graph(),[capability],rule_reviews={'sale':{'status':'approved_human','fingerprint':'v1'}})
    statuses=[r['status'] for r in report['capabilities'][0]['children']]
    assert statuses==['NEEDS_INPUT','PENDING_REVIEW','PENDING_REVIEW']
    report=assess_capabilities(graph(),[capability],approvals={'fact:base'},params={'quantity':1},rule_reviews={'sale':{'status':'approved_human','fingerprint':'v2'}})
    assert report['status']=='AVAILABLE'


def test_conditional_applicability_and_missing_conditions():
    caps=[{'id':'quality','dependencies':{'when':{'quality':'normal'},'then':{'record':'fact:base'}}}]
    assert assess_capabilities(graph(),caps)['capabilities'][0]['status']=='NEEDS_INPUT'
    assert assess_capabilities(graph(),caps,params={'quality':'gold'})['capabilities'][0]['status']=='NOT_APPLICABLE'
    assert assess_capabilities(graph(),caps,params={'quality':'normal'},approvals={'fact:base'})['status']=='AVAILABLE'


def test_selector_uses_runtime_conditions_not_just_identity():
    g=graph();g['facts'][0]['conditions']={'profession':'tiller'}
    selector={'kind':'fact','subject':'entity:A','predicate':'sell_normal','__context':{}}
    cap=[{'id':'sale','dependencies':{'selector':selector}}]
    assert assess_capabilities(g,cap,approvals={'fact:base'})['capabilities'][0]['status']=='NEEDS_INPUT'
    selector['__context']={'profession':'none'}
    assert assess_capabilities(g,cap,approvals={'fact:base'})['capabilities'][0]['status']=='NOT_APPLICABLE'
    selector['__context']={'profession':'tiller'}
    assert assess_capabilities(g,cap,approvals={'fact:base'})['status']=='AVAILABLE'


def test_missing_template_parameter_is_not_invalid_dsl():
    cap=[{'id':'input','dependencies':{'selector':{'kind':'fact','subject':'$entity_id'}}}]
    assert assess_capabilities(graph(),cap)['capabilities'][0]['status']=='NEEDS_INPUT'
    bad=[{'id':'bad','dependencies':{'all':'not a list'}}]
    assert assess_capabilities(graph(),bad)['capabilities'][0]['status']=='INVALID_DEPENDENCY'


def test_dependency_ids_cannot_substitute_entities_for_fact_evidence():
    g=graph();g['entities']=[{'id':'entity:unproven','type':'Item'}]
    g['relations'][0]['support_fact_ids']=['fact:base','entity:unproven']
    result=audit_release_dependencies(g,{'relation:derived','fact:base'})
    assert result['status']=='BLOCKED'
    assert any(r.get('reason')=='DEPENDENCY_TYPE_MISMATCH' for r in result['records'])


def test_publish_retains_only_reviewed_evidence_closure(tmp_path,monkeypatch):
    import copy
    import stardew_agent.knowledge as knowledge
    from stardew_agent.core import read
    # Isolated fixture; no production review, snapshot or pointer is created.
    domain={k:[] for k in ('entities','facts','relations','evidence','assets','occurrences','regions','observations','alignments')}
    domain['facts']=[{'id':'fact:approved','review_status':'candidate','evidence_ids':['evidence:used']},
                     {'id':'fact:unreviewed','review_status':'candidate','evidence_ids':['evidence:unused']}]
    domain['evidence']=[{'id':'evidence:used','quote':'reviewed supporting quotation'},
                        {'id':'evidence:unused','quote':'unreviewed candidate claim'}]
    class SnapshotFixture:
        def __init__(self,*args,**kwargs):self.domain=copy.deepcopy(domain)
    captured={}
    def build_fixture(build_id,**kwargs):
        captured.update(read(tmp_path/'artifacts/builds'/build_id/'fused_graph.json'))
        return {'snapshot_id':'fixture-release'}
    monkeypatch.setattr(knowledge,'Snapshot',SnapshotFixture);monkeypatch.setattr(knowledge,'build_snapshot',build_fixture)
    monkeypatch.setattr(knowledge,'DATA',tmp_path/'data');monkeypatch.setattr(knowledge,'ARTIFACTS',tmp_path/'artifacts')
    review={'snapshot_id':'fixture-parent','decisions':[{'id':'fact:approved','action':'approve','actor':'local_user','reason':'isolated synthetic test'}]}
    result=knowledge.publish('fixture-parent',review)
    assert result['status']=='RELEASED'
    assert [e['id'] for e in captured['evidence']]==['evidence:used']
    assert {e for f in captured['facts'] for e in f['evidence_ids']}=={e['id'] for e in captured['evidence']}
