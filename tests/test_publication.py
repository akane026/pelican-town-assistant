"""Synthetic approval fixtures are restricted to temporary copies, never user reviews."""
import copy,shutil
import pytest
import stardew_agent.knowledge as kg
from stardew_agent.core import read,write,file_hash,ValidationError

@pytest.fixture
def isolated(tmp_path,monkeypatch):
    source=kg.Snapshot(allow_candidate=True)
    dst=tmp_path/'data/snapshots'/source.id;shutil.copytree(source.directory,dst)
    write(tmp_path/'data/latest_candidate.json',{'snapshot_id':source.id})
    # Mimic an existing release pointer; failures must not alter it.
    write(tmp_path/'data/current.json',{'snapshot_id':'previous_release_fixture'})
    monkeypatch.setattr(kg,'DATA',tmp_path/'data');monkeypatch.setattr(kg,'ARTIFACTS',tmp_path/'artifacts')
    fact=source.domain['facts'][0]
    review={'snapshot_id':source.id,'fixture_only':True,'decisions':[{'id':fact['id'],'actor':'local_user','action':'approve','reason':'Synthetic test fixture, not actual human approval.'}]}
    return source,review,tmp_path

def test_publish_subset_is_atomic_and_candidate_unchanged(isolated):
    original,review,tmp=isolated;before=file_hash(tmp/'data/snapshots'/original.id/'manifest.json')
    released=kg.publish(original.id,review);new=kg.Snapshot(released['snapshot_id'])
    assert [r['id'] for r in new.domain['facts']]==[review['decisions'][0]['id']]
    assert not new.domain['relations'] and not new.domain['alignments']
    assert new.roundtrip()['status']=='PASS'
    assert file_hash(tmp/'data/snapshots'/original.id/'manifest.json')==before
    assert read(tmp/'data/latest_candidate.json')['snapshot_id']==original.id
    assert read(tmp/'data/current.json')['snapshot_id']==new.id
    assert kg.publish(original.id,review)['snapshot_id']==new.id

def test_failed_publish_keeps_previous_pointer_and_no_partial_snapshot(isolated,monkeypatch):
    original,review,tmp=isolated
    def fail(*a,**kw):raise OSError('injected exporter failure')
    from semantica.export import JSONExporter
    monkeypatch.setattr(JSONExporter,'export_knowledge_graph',fail)
    with pytest.raises(OSError,match='injected'):kg.publish(original.id,review)
    assert read(tmp/'data/current.json')['snapshot_id']=='previous_release_fixture'
    assert [x.name for x in (tmp/'data/snapshots').iterdir()]==[original.id]
    assert read(tmp/'data/latest_candidate.json')['snapshot_id']==original.id

def test_tampered_review_rejected(isolated):
    original,review,tmp=isolated;released=kg.publish(original.id,review);path=tmp/'data/snapshots'/released['snapshot_id']/'review.json'
    changed=read(path);changed['decisions'][0]['reason']='altered';write(path,changed)
    with pytest.raises(ValidationError,match='REVIEW_FILE_CHANGED'):kg.Snapshot(released['snapshot_id'])

def test_ambiguous_or_unknown_approval_rejected(isolated):
    original,review,tmp=isolated;review['decisions']*=2
    with pytest.raises(ValidationError,match='DUPLICATE_REVIEW'):kg.publish(original.id,review)
    review['decisions']=[{'id':'unknown'}]
    with pytest.raises(ValidationError,match='UNKNOWN_REVIEW'):kg.publish(original.id,review)
