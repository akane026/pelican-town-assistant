import copy,shutil
import pytest
from stardew_agent.core import *
import stardew_agent.construction as build
import stardew_agent.parsing as parsing
import stardew_agent.visual as visual

@pytest.fixture
def isolated_corpus(tmp_path,monkeypatch):
    sources=[s for s in read(DATA/'manifests/sources.json') if s['page_id'] in ('Kale','Garlic')]
    assets=read(DATA/'manifests/assets.json')
    # Isolated copies of actual sources; no live manifests or old results modified.
    for r,field in [(x,'raw_path') for x in sources]+[(x,'path') for x in assets]:
        dest=tmp_path/r[field];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/r[field],dest)
    for name in ('parsing.py','visual.py','construction.py','core.py','model.py'):
        dest=tmp_path/'stardew_agent'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/'stardew_agent'/name,dest)
    write(tmp_path/'configs/corpus.json',{'batch_a':['Kale','Garlic']});write(tmp_path/'configs/aliases.json',{})
    write(tmp_path/'data/manifests/sources.json',sources);write(tmp_path/'data/manifests/assets.json',assets)
    for mod in (build,parsing,visual):monkeypatch.setattr(mod,'ROOT',tmp_path);monkeypatch.setattr(mod,'DATA',tmp_path/'data')
    monkeypatch.setattr(build,'ARTIFACTS',tmp_path/'artifacts')
    monkeypatch.setattr(build,'legacy_rules',lambda:{k:[] for k in ('entities','facts','relations','evidence','assets','occurrences','regions','observations','alignments')})
    return tmp_path,sources,assets

def test_idempotence_and_stale_source_cannot_reuse_checkpoint(isolated_corpus):
    root,sources,_=isolated_corpus
    first=build.build_batch('batch_a','structural',resume=True);second=build.build_batch('batch_a','structural',resume=True)
    assert first['graph_content_hash']==second['graph_content_hash']
    assert all(x['execution']=='checkpoint_reuse' for x in second['pages'])
    p=root/sources[0]['raw_path'];p.write_text(p.read_text()+'<!-- synthetic unregistered source change -->')
    with pytest.raises(ValidationError,match='SOURCE_CHANGED'):build.build_batch('batch_a','structural',resume=True)

def test_single_page_revision_reuses_unchanged_page(isolated_corpus):
    root,sources,_=isolated_corpus
    before=build.build_batch('batch_a','structural',resume=True)
    p=root/sources[0]['raw_path'];p.write_text(p.read_text()+'<!-- synthetic revision fixture -->');sources[0]['sha256']=file_hash(p);sources[0]['revision_id']='synthetic-revision'
    write(root/'data/manifests/sources.json',sources)
    after=build.build_batch('batch_a','structural',resume=True)
    assert after['build_id']!=before['build_id']
    unchanged=next(x for x in after['pages'] if x['page']==sources[1]['page_id'])
    changed=next(x for x in after['pages'] if x['page']==sources[0]['page_id'])
    assert unchanged['execution']=='document_cache_reuse' and changed['status']=='completed'

def test_failed_page_resumes_and_preserves_other_checkpoint(isolated_corpus,monkeypatch):
    root,sources,_=isolated_corpus;real=build.parse_page;failed=set()
    def interrupt(source,assets):
        if source['page_id']==sources[0]['page_id'] and not failed:failed.add(source['page_id']);raise OSError('synthetic interrupted page')
        return real(source,assets)
    monkeypatch.setattr(build,'parse_page',interrupt)
    first=build.build_batch('batch_a','structural',resume=True);second=build.build_batch('batch_a','structural',resume=True)
    assert first['status']=='PARTIAL' and second['status']=='CANDIDATE_BUILT'
    assert any(x.get('execution')=='checkpoint_reuse' for x in second['pages'])
    assert len(second['pages'])==2

def test_changed_asset_bytes_cannot_reuse_manifest(isolated_corpus):
    root,_,assets=isolated_corpus
    build.build_batch('batch_a','structural',resume=True)
    p=root/assets[0]['path'];p.write_bytes(p.read_bytes()+b'synthetic-corruption')
    with pytest.raises(ValidationError,match='ASSET_CHANGED'):build.build_batch('batch_a','structural',resume=True)
