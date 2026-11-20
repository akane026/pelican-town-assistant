"""Real Semantica graph construction and strict, source-aware query adapter."""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
from pathlib import Path
from .common import BASE, DATA, ROOT, assert_record, dump, file_sha, load, now, offline_guard, sha
from .knowledge import SCHEMA

GRAPH = BASE/'artifacts/graph'


class EvidenceError(Exception): pass


def validate_graph(graph):
    ids=[n['id'] for n in graph['entities']]
    if len(ids)!=len(set(ids)):raise EvidenceError('Duplicate node ID')
    for e in graph['relationships']:
        if e['source'] not in ids or e['target'] not in ids:raise EvidenceError('Orphan endpoint')


def build(directory=GRAPH):
    from semantica.kg import GraphBuilder
    from semantica.export import JSONExporter
    from semantica.provenance import ProvenanceManager
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    source=load(DATA/'graph_input.json');validate_graph(source)
    manifest=load(DATA/'knowledge_manifest.json')
    graph=GraphBuilder(merge_entities=False,resolve_conflicts=False,enable_temporal=False,graph_store=None).build(sources=[source],extract=False)
    validate_graph(graph)
    # Require all original fields, allowing Semantica to add derived metadata.
    for group in ('entities','relationships'):
        out={n['id']:n for n in graph[group]}
        for original in source[group]:
            if any(out[original['id']].get(k)!=v for k,v in original.items()):raise EvidenceError('Semantica field changed')
    JSONExporter().export_knowledge_graph(graph,str(directory/'graph.json'),format='json')
    db=directory/'provenance.sqlite3'
    if db.exists(): db.unlink()  # output of this reproducible build only
    pm=ProvenanceManager(storage_path=str(db))
    for n in graph['entities']:
        if n['type']!='Fact':continue
        f=n['metadata'];ev=f['evidence'][0]
        entry=pm.track_entity(entity_id=f['id'],source=ev['url'],source_location=ev['location'],
                             source_quote=ev['quote'],entity_type='Fact',metadata={'fact':f,'snapshot_id':manifest['snapshot_id']})
        if entry is None or not pm.get_provenance(f['id']):raise EvidenceError('Silent provenance failure')
    for e in graph['relationships']:
        if e['metadata'].get('fact_id'):
            f=next(n['metadata'] for n in graph['entities'] if n['id']==e['metadata']['fact_id'])
            ev=f['evidence'][0]
            if pm.track_relationship(relationship_id=e['id'],source=ev['url'],source_location=ev['location'],metadata={'fact_id':f['id']}) is None:
                raise EvidenceError('Relationship provenance failure')
    dump(directory/'manifest.json',{**manifest,'writer_pid':os.getpid(),'graph_sha256':file_sha(directory/'graph.json'),
                                   'provenance_sha256':file_sha(db),'built_at':now()})
    return graph


class KnowledgeGraph:
    def __init__(self,directory=GRAPH, *, expected_snapshot=None, validate_sources=True):
        from semantica.provenance import ProvenanceManager
        self.directory=Path(directory)
        try:
            self.manifest=load(self.directory/'manifest.json')
            if self.manifest['schema']!=SCHEMA:raise EvidenceError('Incompatible schema')
            if expected_snapshot and self.manifest['snapshot_id']!=expected_snapshot:raise EvidenceError('STALE_INDEX')
            for path,key in [('graph.json','graph_sha256'),('provenance.sqlite3','provenance_sha256')]:
                if file_sha(self.directory/path)!=self.manifest[key]:raise EvidenceError('Artifact checksum mismatch: '+path)
            self.graph=load(self.directory/'graph.json');validate_graph(self.graph)
            self.pm=ProvenanceManager(storage_path=str(self.directory/'provenance.sqlite3'))
        except (OSError,ValueError,KeyError) as exc:raise EvidenceError('Missing/corrupt graph dependency') from exc
        self.nodes={n['id']:n for n in self.graph['entities']};self.edges=self.graph['relationships']
        self.facts={n['id']:n['metadata'] for n in self.graph['entities'] if n['type']=='Fact'}
        self.validate_sources=validate_sources

    def fact(self,subject,predicate, *, require_release=False):
        fid='fact:'+subject+':'+predicate
        if fid not in self.facts:raise EvidenceError('INCOMPLETE_EVIDENCE: '+fid)
        f=self.facts[fid]
        if require_release and f['conditions']['version_status']!='verified':raise EvidenceError('UNVERIFIED_GAME_VERSION')
        p=self.pm.get_provenance(fid)
        if not p or p.get('metadata',{}).get('fact')!=f:raise EvidenceError('Missing/mismatched provenance: '+fid)
        valid=[]
        for ev in f['evidence']:
            path=BASE/ev['raw_path']
            if path.exists() and file_sha(path)==ev['source_sha256'] and sha(ev['quote'].encode())==ev['quote_sha256']:
                valid.append(ev)
        if self.validate_sources and not valid:raise EvidenceError('No valid source: '+fid)
        if not f.get('unit') or 'value' not in f:raise EvidenceError('Missing value/unit')
        return {**f,'evidence':valid,'snapshot_id':self.manifest['snapshot_id']}

    def targets(self,subject,kind):
        return [e['target'] for e in self.edges if e['source']==subject and e['type']==kind]

    def seed_crop(self,seed):
        targets=self.targets(seed,'GROWS_INTO')
        f=self.fact(seed,'grows_into')
        if f['value'] not in targets:raise EvidenceError('Missing seed-to-crop edge')
        return f['value']


def read_and_check(directory):
    checks=[];g=KnowledgeGraph(directory);m=g.manifest
    assert_record(checks,'independent_process',m['writer_pid']!=os.getpid())
    src=load(DATA/'graph_input.json')
    for group in ('entities','relationships'):
        out={x['id']:x for x in g.graph[group]}
        assert_record(checks,group+'_all_original_fields',all(all(out[n['id']].get(k)==v for k,v in n.items()) for n in src[group]))
    crop=g.seed_crop('Parsnip_Seeds')
    assert_record(checks,'seed_crop_season_growth',(crop,g.fact(crop,'season')['value'],g.fact(crop,'growth_days')['value'])==('Parsnip','Spring',4))
    stages=g.targets('Melon','HAS_STAGE')
    assert_record(checks,'stage_sequence',len(stages)==6 and [g.fact(s,'duration')['value'] for s in stages]==[1,2,3,3,3,0])
    assert_record(checks,'fact_to_source_and_picture',bool(g.fact('Parsnip','growth_days')['evidence']) and bool(g.targets('Parsnip','DEPICTED_AT')))
    assert_record(checks,'all_facts_provenance',all(g.fact(f['subject'],f['predicate']) for f in g.facts.values()))
    for name,mutate in [
        ('orphan_endpoint',lambda x:x['relationships'].append({'id':'bad','source':'missing','target':'Parsnip'})),
        ('duplicate_id',lambda x:x['entities'].append(x['entities'][0]))]:
        import copy
        bad=copy.deepcopy(g.graph);mutate(bad)
        try:validate_graph(bad);caught=False
        except EvidenceError:caught=True
        assert_record(checks,name+'_rejected',caught)
    # Same display name is not a duplicate identity.
    import copy
    same=copy.deepcopy(g.graph);same['entities'].append({'id':'diagnostic:other_parsnip','name':'Parsnip','type':'Item','metadata':{}})
    validate_graph(same);assert_record(checks,'same_name_distinct_id',True)
    for defect in ['missing_db','corrupt_manifest','incompatible_schema','corrupt_graph']:
        dest=BASE/'artifacts/negative_graph'/defect
        if dest.exists():shutil.rmtree(dest)
        shutil.copytree(directory,dest)
        if defect=='missing_db':(dest/'provenance.sqlite3').unlink()
        elif defect=='corrupt_manifest':(dest/'manifest.json').write_text('{bad')
        elif defect=='incompatible_schema':
            mm=load(dest/'manifest.json');mm['schema']='future/99';dump(dest/'manifest.json',mm)
        else:(dest/'graph.json').write_text('{}')
        try:KnowledgeGraph(dest);caught=False
        except EvidenceError:caught=True
        assert_record(checks,defect+'_rejected',caught)
    original=g.edges;g.edges=[e for e in original if not (e['source']=='Parsnip_Seeds' and e['type']=='GROWS_INTO')]
    try:g.seed_crop('Parsnip_Seeds');caught=False
    except EvidenceError:caught=True
    assert_record(checks,'unique_seed_edge_removal_observed',caught)
    try:
        from semantica.provenance import ProvenanceManager
        pm=ProvenanceManager(storage_path=str(Path(directory)/'graph.json'/'impossible.sqlite'))
        entry=pm.track_entity(entity_id='test',source='fixture',source_location='fixture')
        caught=entry is None
    except Exception:caught=True
    assert_record(checks,'unwritable_provenance_observed',caught)
    result={'status':'PASS' if all(c['passed'] for c in checks) else 'FAIL','fixture':False,'at':now(),
            'assertions':checks,'counts':{'nodes':len(g.nodes),'edges':len(original),'facts':len(g.facts)},
            'writer_pid':m['writer_pid'],'reader_pid':os.getpid(),'snapshot_id':m['snapshot_id'],
            'query_examples':{'seed':crop,'stages':stages,'fact':g.fact('Parsnip','growth_days')}}
    dump(BASE/'results/v02.json',result);print(result['status'],len(checks));return 0 if result['status']=='PASS' else 1


def probe():
    logs=BASE/'logs/graph';logs.mkdir(parents=True,exist_ok=True)
    for step in ('build','read'):
        r=subprocess.run([sys.executable,'-m','verification.graph',step],cwd=ROOT,capture_output=True,text=True)
        (logs/(step+'.log')).write_text(r.stdout+'\n'+r.stderr)
        print(step,r.returncode,r.stdout[-400:])
        if r.returncode:return r.returncode
    return 0


if __name__=='__main__':
    offline_guard()
    if len(sys.argv)==1:raise SystemExit(probe())
    if sys.argv[1]=='build':build()
    elif sys.argv[1]=='read':raise SystemExit(read_and_check(GRAPH))
