import copy
import pytest
from stardew_agent.core import DATA, ROOT, read, digest, file_hash, ident, relation, ValidationError
from stardew_agent.normalization import normalize_graph
from stardew_agent.construction import reconcile_sources, derive_graph, integrate_source_contributions, reconcile_contribution_registry
from stardew_agent.parsing import parse_page, extract_structural
from stardew_agent.knowledge import Snapshot


def document(page='Fixture',revision='one',value=4):
    g={k:[] for k in ('entities','facts','relations','evidence','assets','occurrences','regions','observations','alignments')}
    subject='entity:'+page;evidence='evidence:'+page+revision
    g.update(page_id=page,source_id='source:'+page+revision,
        entities=[{'id':subject,'name':page,'type':'item','page_ids':[page],'aliases':[]}],evidence=[{'id':evidence}],
        facts=[{'id':ident('fact',subject,'growth_days',value,'growth_nights',{}),'subject':subject,'predicate':'growth_days','value':value,'unit':'growth_nights','conditions':{},'evidence_ids':[evidence],'review_status':'candidate'}])
    return g


def test_explicit_migration_updates_all_references_and_preserves_direction_conditions():
    g=document();g['entities'].append({'id':'entity:Fixture_plural','name':'Fixture plural','type':'Item','page_ids':['Other'],'aliases':['alias']})
    f=g['facts'][0];f['subject']='entity:Fixture_plural';f['id']=ident('fact',f['subject'],f['predicate'],f['value'],f['unit'],f['conditions'])
    r=relation('entity:Fixture_plural','RELATED_TO','entity:Fixture',['evidence:Fixtureone'],{'quality':'gold'},support_fact_ids=[f['id']]);g['relations']=[r]
    before=digest(g)
    result=normalize_graph(g,{'type_map':{'item':'Item'},'entity_map':{'entity:Fixture_plural':'entity:Fixture'},'predicate_map':{'RELATED_TO':'CAN_PROCESS'}})
    out=result['graph'];mapping=result['migration']['id_map']
    assert digest(g)==before and len(out['entities'])==1
    assert out['entities'][0]['page_ids']==['Fixture','Other'] and 'Fixture plural' in out['entities'][0]['aliases']
    assert out['relations'][0]['subject']=='entity:Fixture' and out['relations'][0]['conditions']=={'quality':'gold'}
    assert out['relations'][0]['support_fact_ids']==[mapping[f['id']]]
    assert out['relations'][0]['direction']=='forward'
    assert normalize_graph(out,result['migration']['policy'])['graph']==out


def test_unknown_and_plural_entities_remain_unmerged():
    g=document();g['entities'].append({'id':'entity:Fixtures','name':'Fixtures','type':'unmapped_type','page_ids':[],'aliases':[]})
    result=normalize_graph(g)
    assert len(result['graph']['entities'])==2 and any(i['code']=='UNKNOWN_ENTITY_TYPE' for i in result['issues'])
    assert result['migration']['id_map']=={}


def test_cycle_and_unknown_mapping_target_rejected():
    g=document();g['entities'].append({'id':'entity:B','name':'B','type':'Item'})
    for mapping in ({'entity:Fixture':'entity:B','entity:B':'entity:Fixture'},{'entity:Fixture':'entity:missing'}):
        with pytest.raises(ValidationError):normalize_graph(g,{'entity_map':mapping})


def test_revision_replaces_values_and_source_deletion_retracts_records():
    first=document();other=document('Other');updated=document(revision='two',value=9)
    old=digest([first,other]);result=reconcile_sources([first,other],[updated])
    assert sorted(f['value'] for f in result['graph']['facts'])==[4,9]
    assert first['facts'][0]['id'] in result['changes']['withdrawn_record_ids']
    assert not result['graph']['conflicts'] and digest([first,other])==old
    deleted=reconcile_sources(result['documents'],[],['Fixture'])
    assert [f['subject'] for f in deleted['graph']['facts']]==['entity:Other']
    assert deleted['graph']['evidence']==other['evidence']
    empty=copy.deepcopy(updated);empty['facts']=[]
    assert len(reconcile_sources([first,other],[empty])['graph']['facts'])==1


def test_changed_actual_source_value_reparsed(tmp_path):
    sources=read(DATA/'manifests/sources.json');assets=read(DATA/'manifests/assets.json')
    source=next(s for s in sources if s['page_id']=='Kale')
    old=extract_structural(parse_page(source,assets),assets)
    html=(ROOT/source['raw_path']).read_text()
    # Controlled mutation of a real archived source, never a claimed new Wiki revision.
    import re
    changed,count=re.subn(r'(Growth Time</td>\s*<td[^>]*>.*?)6 days',r'\g<1>9 days',html,count=1,flags=re.S)
    assert count==1
    path=tmp_path/'controlled_source_revision.html';path.write_text(changed)
    revision={**source,'revision_id':'synthetic-controlled-revision','raw_path':str(path),'sha256':file_hash(path)}
    new=extract_structural(parse_page(revision,assets),assets)
    result=reconcile_sources([old],[new]);values=[f['value'] for f in result['graph']['facts'] if f['predicate']=='growth_days']
    assert values==[9] and not result['graph']['conflicts']
    assert old['facts']!=new['facts'] and source['sha256']==file_hash(ROOT/source['raw_path'])


def test_actual_source_stage_removal_rebuilds_sequence(tmp_path):
    from bs4 import BeautifulSoup
    source=next(s for s in read(DATA/'manifests/sources.json') if s['page_id']=='Kale');assets=read(DATA/'manifests/assets.json')
    old=extract_structural(parse_page(source,assets),assets)
    soup=BeautifulSoup((ROOT/source['raw_path']).read_text(),'html.parser')
    header=next(x for x in soup.find_all('th') if x.get_text(strip=True)=='Stage 1')
    table=header.find_parent('table')
    for row in table.find_all('tr'):row.find_all(['th','td'],recursive=False)[1].decompose()
    path=tmp_path/'controlled_stage_revision.html';path.write_text(str(soup))
    new=extract_structural(parse_page({**source,'revision_id':'synthetic-stage-removal','raw_path':str(path),'sha256':file_hash(path)},assets),assets)
    result=reconcile_sources([old],[new]);graph=result['graph']
    assert len([e for e in graph['entities'] if e['type']=='CropStage'])==4
    assert len([r for r in graph['relations'] if r['predicate']=='NEXT_STAGE'])==3
    assert any(i.startswith('relation:') for i in result['changes']['withdrawn_record_ids'])
    assert not graph['conflicts'] and source['sha256']==file_hash(ROOT/source['raw_path'])


def test_category_change_and_source_deletion_retract_derived_join():
    category=document('Fruit');formula=document('Wine')
    f=category['facts'][0];f.update(predicate='category',value='fruit',unit='category');f['id']=ident('fact',f['subject'],f['predicate'],f['value'],f['unit'],{})
    p=formula['facts'][0];p.update(predicate='value_formula',value='3*base',unit='g');p['id']=ident('fact',p['subject'],p['predicate'],p['value'],p['unit'],{})
    category['evidence'][0]['quote']='A fruit.';formula['evidence'][0]['quote']='Fruit is processed into wine.'
    before=derive_graph([category,formula]);derived=next(r for r in before['relations'] if r['predicate']=='CAN_PROCESS')
    changed=copy.deepcopy(category);changed['source_id']='source:revision-two';changed['facts'][0]['value']='vegetable'
    f=changed['facts'][0];f['id']=ident('fact',f['subject'],f['predicate'],f['value'],f['unit'],{})
    result=reconcile_sources([category,formula],[changed])
    assert not result['graph']['relations'] and derived['id'] in result['changes']['withdrawn_record_ids']
    assert not reconcile_sources([category,formula],[],['Wine'])['graph']['relations']


def test_derived_category_join_is_evidence_order_independent_and_rejects_conflict():
    category=document('Fruit');formula=document('Wine')
    f=category['facts'][0];f.update(predicate='category',value='fruit',unit='category')
    f['id']=ident('fact',f['subject'],f['predicate'],f['value'],f['unit'],{})
    p=formula['facts'][0];p.update(predicate='value_formula',value='3*base',unit='g')
    p['id']=ident('fact',p['subject'],p['predicate'],p['value'],p['unit'],{})
    category['evidence'][0]['quote']='A fruit.';formula['evidence'][0]['quote']='The product price uses base value.'
    formula['evidence'].append({'id':'evidence:input','quote':'Fruit is processed into the product.'})
    p['evidence_ids'].append('evidence:input')
    first=derive_graph([category,formula]);p['evidence_ids'].reverse();second=derive_graph([category,formula])
    assert [r['id'] for r in first['relations']]==[r['id'] for r in second['relations']] and len(first['relations'])==1
    formula['evidence'].append({'id':'evidence:contradiction','quote':'Vegetables are processed into the product.'})
    p['evidence_ids'].append('evidence:contradiction')
    assert not derive_graph([category,formula])['relations']


def test_entity_unit_names_resolve_only_unique_known_identity():
    g=document();g['entities'].append({'id':'entity:Keg','name':'Keg','type':'Equipment'})
    f=g['facts'][0];f.update(predicate='equipment',unit='entity',value='Keg');old=f['id']
    result=normalize_graph(g)
    assert result['graph']['facts'][0]['value']=='entity:Keg' and old in result['migration']['id_map']
    g['entities'].append({'id':'entity:AmbiguousKeg','name':'Keg','type':'Item'})
    result=normalize_graph(g)
    assert result['graph']['facts'][0]['value']=='Keg' and any(i['code']=='AMBIGUOUS_ENTITY_VALUE' for i in result['issues'])


def test_source_withdrawal_invalidates_approval_of_changed_evidence_union():
    first=document();second=document('Other')
    second['entities'][0].update(id=first['entities'][0]['id'],name='Fixture')
    second['facts'][0].update(id=first['facts'][0]['id'],subject=first['facts'][0]['subject'])
    # Synthetic reviewer fixture stays in memory, no review file or release written.
    first['facts'][0].update(review_status='approved_human',answer_allowed=True,approval={'actor':'local_user','action':'approve','reason':'isolated fixture'})
    result=reconcile_sources([first,second],[],['Other'])
    row=result['graph']['facts'][0]
    assert row['evidence_ids']==first['facts'][0]['evidence_ids']
    assert row['review_status']=='candidate' and row['answer_allowed'] is False and 'approval' not in row


def test_duplicate_source_records_deduplicate_only_equivalent_payloads():
    source=document();source['evidence'].append(copy.deepcopy(source['evidence'][0]))
    result=reconcile_sources([],[source]);assert len(result['graph']['evidence'])==1
    assert result['documents'][0]['canonicalization']['duplicate_counts']=={'evidence':1}
    source['evidence'][1]['quote']='different meaning under reused ID'
    with pytest.raises(ValidationError,match='SOURCE_RECORD_ID_COLLISION'):reconcile_sources([],[source])


def test_incremental_aggregate_entry_keeps_original_layer_explicit():
    base=document();base['evidence'][0]['page_id']='Fixture'
    new=document('New')
    imported=integrate_source_contributions(base,[],[new])
    assert len(imported['graph']['facts'])==2 and imported['source_layers']['replaceable_page_ids']==['New']
    removed=integrate_source_contributions(base,imported['documents'],[],['New'])
    assert removed['graph']['facts']==base['facts']
    with pytest.raises(ValidationError,match='AGGREGATE_SOURCE_REQUIRES_ORIGINAL_CONTRIBUTION'):
        integrate_source_contributions(base,[],[document(revision='new')])


def test_recovered_component_retracts_on_real_source_binding_change():
    first=document();other=document('Other')
    for source in (first,other):
        source['evidence'][0].update(page_id=source['page_id'],source_id=source['source_id'])
    graph={k:[] for k in ('entities','facts','relations','evidence','assets','occurrences','regions','observations','alignments')}
    graph.update(entities=first['entities']+other['entities'],evidence=first['evidence']+other['evidence'],
        relations=[relation('entity:Fixture','RELATED_TO','entity:Other',[e['id'] for e in first['evidence']+other['evidence']],support_fact_ids=[first['facts'][0]['id'],other['facts'][0]['id']])])
    component={'id':'isolated-fixture-component','graph':graph,'source_bindings':[{'page_id':d['page_id'],'source_id':d['source_id']} for d in (first,other)]}
    good=reconcile_contribution_registry([first,other],[],components=[component])
    assert good['component_status'][0]['status']=='ACTIVE' and len(good['graph']['relations'])==1
    changed=document(revision='two',value=9);changed['evidence'][0].update(page_id=changed['page_id'],source_id=changed['source_id'])
    result=reconcile_contribution_registry([first,other],[changed],components=[component])
    assert result['component_status'][0]['status']=='WITHDRAWN_STALE_SOURCE' and not result['graph']['relations']
    assert len(result['graph']['facts'])==2
    removed=reconcile_contribution_registry([first,other],[],['Fixture'],[component])
    assert removed['graph']['facts']==other['facts'] and not removed['graph']['relations']


def test_legacy_snapshot_unchanged_and_normalization_is_idempotent():
    # This checks migration of the immutable pre-ROI baseline, independently
    # of which newer candidate the workbench currently has activated.
    snapshot=Snapshot('0f47248587aed45b1fc0887be608e3bd8ad429f79e363e841c4b828dcd7b2ac0',allow_candidate=True)
    path=snapshot.directory/'graph.json';before=file_hash(path)
    result=normalize_graph(snapshot.domain);again=normalize_graph(result['graph'])
    assert result['graph']==again['graph'] and file_hash(path)==before
    levels={a['confirmation_level'] for a in result['graph']['alignments']}
    assert 'legacy_model_candidate' in levels and 'visual_checked' not in levels
    Snapshot(snapshot.id,allow_candidate=True)
