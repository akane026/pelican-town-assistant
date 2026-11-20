from __future__ import annotations
import copy, os, shutil, tempfile
from collections import Counter
from pathlib import Path
from .core import *

def validate_evidence(evidence):
    checked={}
    for e in evidence:
        p=contained(ROOT/e['raw_path'])
        if str(p) not in checked:checked[str(p)]=file_hash(p)
        if checked[str(p)]!=e['source_sha256']:raise ValidationError('SOURCE_HASH_MISMATCH')
        if digest(e['quote'].encode())!=e['quote_sha256']:raise ValidationError('QUOTE_HASH_MISMATCH')
    return True


def validate_region_files(domain):
    """Verify stored ROI bytes are the declared crop of the frozen source asset."""
    from PIL import Image
    assets={a['id']:a for a in domain.get('assets',[])}
    for region in domain.get('regions',[]):
        if not region.get('path'):continue
        path=contained(ROOT/region['path'])
        if not path.is_file() or file_hash(path)!=region.get('sha256'):raise ValidationError('REGION_FILE_CHANGED')
        asset=assets[region['asset_id']]
        with Image.open(ROOT/asset['path']) as source, Image.open(path) as crop:
            box=region['bbox'];xy=(int(box[0]*source.width),int(box[1]*source.height),int(box[2]*source.width),int(box[3]*source.height))
            expected=source.crop(xy).convert('RGBA');actual=crop.convert('RGBA')
            if actual.size!=expected.size or actual.tobytes()!=expected.tobytes():raise ValidationError('REGION_PIXELS_MISMATCH')
    return True

def semantica_input(domain):
    entities=[];edges=[];seen=set()
    type_map={'entities':None,'facts':'Fact','relations':'Relation','evidence':'Evidence','assets':'ImageAsset',
              'occurrences':'ImageOccurrence','regions':'ImageRegion','observations':'VisualObservation','alignments':'VisualAlignment'}
    for group,kind in type_map.items():
        for row in domain[group]:
            if row['id'] in seen:raise ValidationError('CROSS_TYPE_DUPLICATE')
            entities.append({'id':row['id'],'name':row.get('name',row['id']),'type':kind or row['type'],'metadata':{'record_type':group,'record':row}});seen.add(row['id'])
    def edge(s,p,t):
        if not s or not t:return
        if s not in seen or t not in seen:raise ValidationError('SEMANTIC_ENDPOINT')
        edges.append({'id':ident('edge',s,p,t),'source':s,'target':t,'type':p,'metadata':{'direction':'forward'}})
    for r in domain['relations']:edge(r['subject'],'HAS_RELATION',r['id']);edge(r['id'],'OBJECT',r['object'])
    for f in domain['facts']:edge(f['subject'],'HAS_FACT',f['id'])
    for r in domain['regions']:edge(r['id'],'REGION_OF',r['asset_id'])
    for o in domain['occurrences']:edge(o['id'],'OCCURRENCE_OF',o.get('asset_id'))
    for o in domain['observations']:
        edge(o['id'],'OBSERVES',o['asset_id'])
        for obj in o['objects']:edge(o['id'],'OBSERVES_REGION',obj['region_id'])
    for a in domain['alignments']:
        edge(a['id'],'ALIGNS_TO',a['target_id']);edge(a['id'],'IN_CONTEXT',a.get('occurrence_id'));edge(a['id'],'OBSERVED_BY',a.get('observation_id'))
        for rid in a['region_ids']:edge(a['id'],'DEPICTS_REGION',rid)
    for group in ('facts','relations','alignments'):
        for rec in domain[group]:
            for eid in rec['evidence_ids']:edge(rec['id'],'SUPPORTED_BY',eid)
            if rec.get('dependency_contract')=='v1':
                from .capabilities import record_dependencies
                for rid in record_dependencies(rec):edge(rec['id'],'DERIVED_FROM',rid)
    return {'entities':entities,'relationships':list({e['id']:e for e in edges}.values())}

def build_snapshot(build_id,*,release_review=None,activate=True,migration=None):
    directory=ARTIFACTS/'builds'/build_id;domain=read(directory/'fused_graph.json');validate_graph(domain);validate_evidence(domain['evidence'])
    for a in domain['assets']:
        if file_hash(ROOT/a['path'])!=a['sha256']:raise ValidationError('ASSET_HASH_MISMATCH')
    validate_region_files(domain)
    from semantica.kg import GraphBuilder
    from semantica.export import JSONExporter
    from semantica.provenance import ProvenanceManager
    payload=semantica_input(domain)
    identity={'schema':SCHEMA,'graph':payload,'sources':domain['evidence'],'assets':domain['assets'],'adapter':'semantica-v3.1'}
    if release_review is not None:identity['review']=release_review
    if migration is not None:identity['migration_hash']=digest(migration)
    snapshot_id=digest(identity)
    dest=DATA/'snapshots'/snapshot_id
    if (dest/'manifest.json').exists():
        existing=Snapshot(snapshot_id,allow_candidate=True).manifest
        if activate and release_review is None:write(DATA/'latest_candidate.json',{'snapshot_id':snapshot_id})
        return existing
    dest.parent.mkdir(parents=True,exist_ok=True);tmp=Path(tempfile.mkdtemp(prefix='.build-',dir=dest.parent))
    try:
        graph=GraphBuilder(merge_entities=False,resolve_conflicts=False,enable_temporal=False,graph_store=None).build(sources=[payload],extract=False)
        for group in ('entities','relationships'):
            got={n['id']:n for n in graph[group]}
            for original in payload[group]:
                if any(got.get(original['id'],{}).get(k)!=v for k,v in original.items()):raise ValidationError('SEMANTICA_FIELD_LOSS')
        JSONExporter().export_knowledge_graph(graph,str(tmp/'graph.json'),format='json')
        pm=ProvenanceManager(storage_path=str(tmp/'provenance.sqlite3'));evs={e['id']:e for e in domain['evidence']}
        for group in ('facts','relations','alignments'):
            for rec in domain[group]:
                ev=evs[rec['evidence_ids'][0]]
                result=pm.track_entity(entity_id=rec['id'],source=ev['url'],source_location=ev['locator'],source_quote=ev['quote'],entity_type=group,
                                       metadata={'record':rec,'snapshot_id':snapshot_id,'all_evidence':[evs[e] for e in rec['evidence_ids']]})
                if result is None or pm.get_provenance(rec['id']).get('metadata',{}).get('record')!=rec:raise ValidationError('PROVENANCE_WRITE_FAILED')
        index={'snapshot_id':snapshot_id,'graph_content_hash':digest(payload),'entity_ids':[n['id'] for n in domain['entities']],
               'relation_ids':[n['id'] for n in domain['relations']],'asset_ids':[a['id'] for a in domain['assets']],'method':'lexical-template/v3.1'}
        write(tmp/'index.json',index)
        write(tmp/'quality.json',{'conflicts':domain.get('conflicts',[]),'human_approved':sum(len(domain[k]) for k in ('facts','relations','alignments')) if release_review is not None else 0,'review_status':'reviewed_subset' if release_review is not None else 'pending'})
        manifest={'snapshot_id':snapshot_id,'build_id':build_id,'schema_version':SCHEMA,'adapter_version':'semantica-v3.1','semantica_version':'0.7.0',
          'release_status':'candidate','writer_pid':os.getpid(),'graph_content_hash':digest(payload),'graph_hash':file_hash(tmp/'graph.json'),
          'provenance_hash':file_hash(tmp/'provenance.sqlite3'),'index_manifest_hash':file_hash(tmp/'index.json'),
          'source_manifest_hash':digest(domain['evidence']),'asset_manifest_hash':digest(domain['assets']),
          'code_hash':digest({p.name:file_hash(p) for p in (ROOT/'stardew_agent').glob('*.py')}),
          'counts':{k:len(v) for k,v in domain.items()},'entity_count_by_type':dict(Counter(n['type'] for n in domain['entities'])),
          'alignment_count_by_method':dict(Counter(n['method'] for n in domain['alignments'])),
          'limitations':['Human approval pending; candidate diagnostic use only.','Game version unverified; source revisions frozen.']}
        if release_review is not None:
            write(tmp/'review.json',release_review)
            manifest.update(release_status='released',review_hash=file_hash(tmp/'review.json'),
                parent_snapshot_id=release_review['snapshot_id'],limitations=['Human-reviewed subset; bound to frozen Wiki revisions; game version unverified.'])
        if migration is not None:
            write(tmp/'migration.json',migration)
            manifest.update(migration_hash=digest(migration),migration_file_hash=file_hash(tmp/'migration.json'),
                            parent_snapshot_id=migration['parent_snapshot_id'],normalization_policy_hash=migration['policy_hash'])
        write(tmp/'manifest.json',manifest);os.replace(tmp,dest)
    except Exception:
        shutil.rmtree(tmp,ignore_errors=True);raise
    if release_review is None and activate:write(DATA/'latest_candidate.json',{'snapshot_id':snapshot_id})
    return manifest


def normalize_snapshot(snapshot_id, policy=None, activate=False):
    """Build and round-trip a new Semantica candidate, leaving the source immutable."""
    from .normalization import normalize_graph
    from .knowledge_quality import audit_graph
    snapshot=Snapshot(snapshot_id,allow_candidate=True)
    result=normalize_graph(snapshot.domain,policy)
    migration={**result['migration'],'parent_snapshot_id':snapshot.id}
    build_id='normalized-'+digest(migration)[:20];directory=ARTIFACTS/'builds'/build_id
    write(directory/'fused_graph.json',result['graph']);write(directory/'migration.json',migration)
    write(directory/'quality.json',audit_graph(result['graph']))
    manifest=build_snapshot(build_id,activate=False,migration=migration)
    check=Snapshot(manifest['snapshot_id'],allow_candidate=True).roundtrip()
    if check['status']!='PASS':raise ValidationError('MIGRATED_SNAPSHOT_ROUNDTRIP_FAILED')
    if activate:write(DATA/'latest_candidate.json',{'snapshot_id':manifest['snapshot_id']})
    return {'status':'CANDIDATE_BUILT','build_id':build_id,'snapshot_id':manifest['snapshot_id'],
            'parent_snapshot_id':snapshot.id,'activated':activate,'migration':migration,'issues':result['issues'],'roundtrip':check}

class Snapshot:
    def __init__(self,snapshot_id=None,allow_candidate=False,validate_files=True):
        if snapshot_id is None:
            p=DATA/('latest_candidate.json' if allow_candidate else 'current.json')
            if not p.exists():raise ValidationError('NO_RELEASED_SNAPSHOT')
            snapshot_id=read(p)['snapshot_id']
        if not isinstance(snapshot_id,str) or len(snapshot_id)!=64 or any(c not in '0123456789abcdef' for c in snapshot_id):raise ValidationError('BAD_SNAPSHOT_ID')
        self.directory=DATA/'snapshots'/snapshot_id;self.manifest=read(self.directory/'manifest.json');self.id=snapshot_id
        if self.manifest['snapshot_id']!=snapshot_id:raise ValidationError('SNAPSHOT_ID_MISMATCH')
        if self.manifest['release_status']!='released' and not allow_candidate:raise ValidationError('UNRELEASED_KNOWLEDGE')
        if 'migration_hash' in self.manifest:
            mp=self.directory/'migration.json'
            if not mp.is_file() or file_hash(mp)!=self.manifest.get('migration_file_hash') or digest(read(mp))!=self.manifest['migration_hash']:raise ValidationError('MIGRATION_FILE_CHANGED')
        release_review=None
        if self.manifest['release_status']=='released':
            review_path=self.directory/'review.json'
            if not review_path.is_file() or file_hash(review_path)!=self.manifest.get('review_hash'):raise ValidationError('REVIEW_FILE_CHANGED')
            release_review=read(review_path)
            if release_review.get('snapshot_id')!=self.manifest.get('parent_snapshot_id'):raise ValidationError('REVIEW_PARENT_MISMATCH')
        for name,key in [('graph.json','graph_hash'),('provenance.sqlite3','provenance_hash'),('index.json','index_manifest_hash')]:
            if file_hash(self.directory/name)!=self.manifest[key]:raise ValidationError('SNAPSHOT_FILE_CHANGED:'+name)
        self.index=read(self.directory/'index.json')
        if self.index['snapshot_id']!=snapshot_id or self.index['graph_content_hash']!=self.manifest['graph_content_hash']:raise ValidationError('STALE_INDEX')
        graph=read(self.directory/'graph.json');domain={k:[] for k in ('entities','facts','relations','evidence','assets','occurrences','regions','observations','alignments')}
        for node in graph['entities']:domain[node['metadata']['record_type']].append(node['metadata']['record'])
        self.records=validate_graph(domain);self.domain=domain
        if digest(domain['evidence'])!=self.manifest['source_manifest_hash'] or digest(domain['assets'])!=self.manifest['asset_manifest_hash']:raise ValidationError('SOURCE_OR_ASSET_MANIFEST_CHANGED')
        if digest(semantica_input(domain))!=self.manifest['graph_content_hash']:raise ValidationError('GRAPH_SEMANTICS_CHANGED')
        if release_review is not None:
            decisions={r['id']:r for r in release_review.get('decisions',[])}
            for k in ('facts','relations','alignments'):
                for row in domain[k]:
                    approval=decisions.get(row['id'],{})
                    if row.get('review_status')!='approved_human' or not row.get('answer_allowed') or row.get('approval')!=approval or approval.get('actor')!='local_user' or approval.get('action')!='approve' or not str(approval.get('reason','')).strip():raise ValidationError('RELEASE_CONTAINS_UNAPPROVED_RECORD')
            from .capabilities import audit_release_dependencies
            if audit_release_dependencies(domain,set(decisions))['status']!='PASS':raise ValidationError('RELEASE_DEPENDENCIES_UNSATISFIED')
            identity={'schema':SCHEMA,'graph':semantica_input(domain),'sources':domain['evidence'],'assets':domain['assets'],'adapter':'semantica-v3.1','review':release_review}
            if 'migration_hash' in self.manifest:identity['migration_hash']=self.manifest['migration_hash']
            if digest(identity)!=self.id:raise ValidationError('RELEASE_ID_MISMATCH')
        if validate_files:
            validate_evidence(domain['evidence'])
            for a in domain['assets']:
                if file_hash(ROOT/a['path'])!=a['sha256']:raise ValidationError('ASSET_CHANGED')
            validate_region_files(domain)
        self.adj={}
        for r in domain['relations']:self.adj.setdefault(r['subject'],[]).append(r)
    def find(self,subject,predicate):return [f for f in self.domain['facts'] if f['subject']==subject and f['predicate']==predicate]
    def roundtrip(self):
        from semantica.provenance import ProvenanceManager
        pm=ProvenanceManager(storage_path=str(self.directory/'provenance.sqlite3'))
        checks=[]
        for group in ('facts','relations','alignments'):
            for row in self.domain[group]:
                p=pm.get_provenance(row['id']);checks.append(bool(p and p.get('metadata',{}).get('record')==row))
        return {'status':'PASS' if all(checks) else 'FAIL','provenance_records_checked':len(checks),'reader_pid':os.getpid(),
                'writer_pid':self.manifest['writer_pid'],'independent_process':os.getpid()!=self.manifest['writer_pid'],
                'counts':{k:len(v) for k,v in self.domain.items()}}

def review_export(snapshot_id):
    s=Snapshot(snapshot_id,allow_candidate=True);queue=[]
    for group in ('facts','relations','alignments'):
        for row in s.domain[group]:
            from .capabilities import record_dependencies
            queue.append({'id':row['id'],'record_type':group,'candidate':row,'evidence':[s.records['evidence'][e] for e in row['evidence_ids']],
                          'dependency_ids':record_dependencies(row),
                          'images':[s.records['regions'][rid] for rid in row.get('region_ids',[])],
                          'action':None,'actor':None,'reason':None})
    path=ARTIFACTS/'review'/snapshot_id;write(path/'queue.json',{'snapshot_id':snapshot_id,'status':'PENDING_HUMAN','items':queue})
    # Short queue links to complete records; no fabricated signatures or defaults to approve.
    compact={'snapshot_id':snapshot_id,'status':'PENDING_HUMAN','count':len(queue),'items':queue[:16],
             'full_queue':str((path/'queue.json').relative_to(ROOT))}
    write(path/'compact.json',compact);return compact

def publish(snapshot_id,review):
    s=Snapshot(snapshot_id,allow_candidate=True)
    if review.get('snapshot_id')!=snapshot_id:raise ValidationError('REVIEW_SNAPSHOT_MISMATCH')
    decisions=review.get('decisions',[])
    critical=[r for k in ('facts','relations','alignments') for r in s.domain[k]]
    known={r['id'] for r in critical}
    if any(r.get('id') not in known for r in decisions):raise ValidationError('UNKNOWN_REVIEW_RECORD')
    if len({r['id'] for r in decisions})!=len(decisions):raise ValidationError('DUPLICATE_REVIEW_DECISION')
    approvals={r['id']:r for r in decisions if r.get('action')=='approve' and r.get('actor')=='local_user' and str(r.get('reason','')).strip()}
    valid={r['id'] for r in critical if r['id'] in approvals and r.get('review_status')!='conflicted'}
    if not valid:return {'status':'BLOCKED','reason':'HUMAN_REVIEW_REQUIRED','missing_count':len(critical),'missing_ids':[r['id'] for r in critical[:20]]}
    from .capabilities import audit_release_dependencies
    dependency_audit=audit_release_dependencies(s.domain,valid)
    if dependency_audit['status']!='PASS':
        return {'status':'BLOCKED','reason':'RELEASE_DEPENDENCIES_UNSATISFIED','dependency_audit':dependency_audit}
    unresolved=[r['id'] for r in s.domain['alignments'] if r['id'] in valid and r.get('status')!='matched']
    if unresolved:return {'status':'BLOCKED','reason':'ALIGNMENT_RESOLUTION_REQUIRED','record_ids':unresolved}
    # Keep candidate snapshot immutable. A separately hashed reviewed build creates the release.
    domain=copy.deepcopy(s.domain)
    for k in ('facts','relations','alignments'):
        domain[k]=[r for r in domain[k] if r['id'] in valid]
        for r in domain[k]:r.update(review_status='approved_human',answer_allowed=True,approval=approvals[r['id']])
    retained_targets={r['id'] for k in ('entities','facts','relations') for r in domain[k]}
    domain['alignments']=[r for r in domain['alignments'] if r['target_id'] in retained_targets]
    # Only reviewed critical records can expose source quotations in a release.
    # Keeping all candidate Evidence nodes would bypass the reviewed subset via
    # the direct evidence lookup endpoint even though facts were filtered.
    retained_evidence={eid for k in ('facts','relations','alignments') for r in domain[k] for eid in r['evidence_ids']}
    domain['evidence']=[e for e in domain['evidence'] if e['id'] in retained_evidence]
    bid=ident('reviewed',snapshot_id,review).split(':')[1];d=ARTIFACTS/'builds'/bid
    write(d/'fused_graph.json',domain);m=build_snapshot(bid,release_review=review)
    Snapshot(m['snapshot_id'])
    write(DATA/'current.json',{'snapshot_id':m['snapshot_id']});return {'status':'RELEASED','snapshot_id':m['snapshot_id']}
