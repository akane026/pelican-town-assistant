import copy,shutil
import pytest
from stardew_agent.core import *
from stardew_agent.knowledge import Snapshot,semantica_input,publish,review_export

def test_real_semantica_roundtrip_multimodal():
    s=Snapshot(allow_candidate=True)
    assert s.roundtrip()['status']=='PASS'
    assert len(s.records['regions'])>0 and len(s.records['observations'])>0
    assert any(a['target_kind']=='state' for a in s.domain['alignments'])
    assert all(r['direction']=='forward' for r in s.domain['relations'])

def test_unapproved_snapshot_and_forged_review_rejected():
    s=Snapshot(allow_candidate=True)
    with pytest.raises(ValidationError,match='UNRELEASED'):Snapshot(s.id)
    result=publish(s.id,{'snapshot_id':s.id,'decisions':[{'id':f['id'],'action':'approve','actor':'model','reason':'looks good'} for f in s.domain['facts']]})
    assert result['status']=='BLOCKED'

def test_relation_reification_keeps_multiple_predicates():
    empty={k:[] for k in ('entities','facts','relations','evidence','assets','occurrences','regions','observations','alignments')}
    empty['entities']=[{'id':n,'name':n,'type':'Synthetic'} for n in ('a','b')]
    empty['evidence']=[{'id':'ev:synthetic'}]
    empty['relations']=[relation('a',p,'b',['ev:synthetic']) for p in ('P','Q')]+[relation('b','P','a',['ev:synthetic'])]
    kg=semantica_input(empty)
    assert sum(n['type']=='Relation' for n in kg['entities'])==3
    assert sum(e['type']=='OBJECT' for e in kg['relationships'])==3

def test_stale_index_rejected(tmp_path,monkeypatch):
    import stardew_agent.knowledge as kg
    original=Snapshot(allow_candidate=True);dest=tmp_path/'snapshots'/original.id;shutil.copytree(original.directory,dest)
    index=read(dest/'index.json');index['snapshot_id']='0'*64;write(dest/'index.json',index)
    m=read(dest/'manifest.json');m['index_manifest_hash']=file_hash(dest/'index.json');write(dest/'manifest.json',m)
    monkeypatch.setattr(kg,'DATA',tmp_path)
    with pytest.raises(ValidationError,match='STALE_INDEX'):kg.Snapshot(original.id,allow_candidate=True)

def test_review_has_source_and_images_not_signature():
    s=Snapshot(allow_candidate=True);q=review_export(s.id)
    assert q['status']=='PENDING_HUMAN'
    assert all(i['actor'] is None and i['action'] is None for i in q['items'])
    assert all(i['evidence'] for i in q['items'])
