"""Replayable candidate import of complete source contributions; never activates."""
from __future__ import annotations
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stardew_agent.core import ROOT,DATA,ARTIFACTS,read,write,file_hash,digest,ValidationError
from stardew_agent.knowledge import Snapshot,build_snapshot
from stardew_agent.construction import integrate_source_contributions,reconcile_contribution_registry
from stardew_agent.normalization import normalize_graph,DEFAULT_POLICY
from stardew_agent.knowledge_quality import audit_graph
from stardew_agent.capabilities import GROUPS


def delta(before,after):
    output={}
    for group in GROUPS:
        left={r['id']:r for r in before.get(group,[])};right={r['id']:r for r in after.get(group,[])}
        output[group]={'added':sorted(right.keys()-left.keys()),'withdrawn':sorted(left.keys()-right.keys()),
            'changed':sorted(i for i in left.keys()&right.keys() if left[i]!=right[i]),
            'reused':sorted(i for i in left.keys()&right.keys() if left[i]==right[i])}
    derived_methods={'source_grounded_category_join','stage_sequence_illustration/v1'}
    def derived(graph):return [r for group in ('relations','alignments') for r in graph[group] if r.get('method') in derived_methods]
    old=derived(before);new=derived(after)
    def semantic(row):return digest({k:row.get(k) for k in ('subject','predicate','object','conditions','target_id','occurrence_id','support_occurrence_ids','region_ids','evidence_ids','support_fact_ids','support_alignment_ids')})
    old_keys={semantic(r):r for r in old};new_keys={semantic(r):r for r in new}
    output['derived']={'recomputed_count':len(new),'semantic_added':[new_keys[k]['id'] for k in sorted(new_keys.keys()-old_keys.keys())],
        'semantic_withdrawn':[old_keys[k]['id'] for k in sorted(old_keys.keys()-new_keys.keys())],
        'semantically_retained':len(old_keys.keys()&new_keys.keys()),
        'identity_rekeyed':sum(old_keys[k]['id']!=new_keys[k]['id'] for k in old_keys.keys()&new_keys.keys())}
    return output


def run(base_id,previous_registry,document_paths,removed_pages,label):
    base=Snapshot(base_id,allow_candidate=True)
    prior=read(previous_registry) if previous_registry else None
    if prior and prior['identity']['base_snapshot_id']!=base_id:raise ValidationError('REGISTRY_BASE_MISMATCH')
    before=Snapshot(prior['snapshot_id'],allow_candidate=True) if prior else base
    frozen={str(p.relative_to(ROOT)):file_hash(p) for p in [DATA/'latest_candidate.json',DATA/'manifests/sources.json',DATA/'manifests/assets.json',
             base.directory/'graph.json',base.directory/'manifest.json',base.directory/'provenance.sqlite3'] if p.exists()}
    previous=[]
    for row in prior['identity']['documents'] if prior else []:
        path=ROOT/row['path']
        if file_hash(path)!=row['file_sha256']:raise ValidationError('CONTRIBUTION_FILE_CHANGED')
        document=read(path)
        if digest(document)!=row['document_hash']:raise ValidationError('CONTRIBUTION_CONTENT_CHANGED')
        previous.append(document)
    updates=[read(ROOT/p) for p in document_paths]
    origins={row['page_id']:row.get('lineage',{'kind':'previous_registry_contribution','registry_hash':prior['registry_hash'],'path':row['path']}) for row in prior['identity']['documents']} if prior else {}
    for path,document in zip(document_paths,updates):
        origins[document['page_id']]={'kind':'complete_source_document_import','inputs':[{'path':str((ROOT/path).resolve().relative_to(ROOT)),
            'file_sha256':file_hash(ROOT/path),'document_hash':digest(document)}]}
    recovered=bool(prior and prior['identity']['base_layer_kind']=='recovered_source_components')
    components=[]
    if recovered:
        for row in prior['identity'].get('components',[]):
            path=ROOT/row['path']
            if file_hash(path)!=row['file_sha256']:raise ValidationError('COMPONENT_FILE_CHANGED')
            components.append(read(path))
        result=reconcile_contribution_registry(previous,updates,removed_pages,components)
    else:result=integrate_source_contributions(base.domain,previous,updates,removed_pages)
    descriptors=[]
    for document in result['documents']:
        checksum=digest(document);path=DATA/'post_midterm/source_contributions'/document['page_id']/(checksum+'.json')
        if path.exists() and read(path)!=document:raise ValidationError('IMMUTABLE_CONTRIBUTION_COLLISION')
        if not path.exists():write(path,document)
        source=document.get('source',{})
        descriptors.append({'page_id':document['page_id'],'source_id':document['source_id'],'document_hash':checksum,
            'path':str(path.relative_to(ROOT)),'file_sha256':file_hash(path),'source_sha256':source.get('sha256'),
            'raw_path':source.get('raw_path'),'revision_id':source.get('revision_id'),'capture_kind':source.get('capture_kind','historical_source_manifest'),
            'lineage':origins[document['page_id']]})
    normalized=normalize_graph(result['graph'])
    identity={'schema':'source-contribution-registry/v1','base_snapshot_id':base.id,'base_graph_content_hash':base.manifest['graph_content_hash'],
        'base_layer_kind':'recovered_source_components' if recovered else 'immutable_aggregate_snapshot','documents':descriptors,'policy_hash':digest(DEFAULT_POLICY),
        'replaceable_page_ids':result['source_layers']['replaceable_page_ids'],'aggregate_page_ids':result['source_layers']['aggregate_page_ids']}
    if recovered:
        identity['components']=prior['identity']['components'];identity['component_status']=result['component_status']
    registry_hash=digest(identity)
    unchanged=bool(prior and registry_hash==prior['registry_hash'] and {k:normalized['graph'][k] for k in GROUPS}==before.domain)
    build_id=prior['build_id'] if unchanged else label+'-'+digest({'parent_snapshot_id':before.id,'registry_hash':registry_hash,'graph':normalized['graph']})[:20]
    directory=ARTIFACTS/'builds'/build_id
    migration={**normalized['migration'],'parent_snapshot_id':before.id,'base_snapshot_id':base.id,'source_registry_hash':registry_hash,
        'import_kind':'incremental_complete_document_contributions','base_layer_kind':identity['base_layer_kind']}
    if unchanged:manifest=before.manifest
    else:
        write(directory/'fused_graph.json',normalized['graph']);write(directory/'migration.json',migration);write(directory/'quality.json',audit_graph(normalized['graph']))
        manifest=build_snapshot(build_id,activate=False,migration=migration)
    snapshot=Snapshot(manifest['snapshot_id'],allow_candidate=True);roundtrip=snapshot.roundtrip()
    registry={'identity':identity,'registry_hash':registry_hash,'snapshot_id':snapshot.id,'build_id':build_id,
        'limitation':result['source_layers']['limitation']}
    artifact=ARTIFACTS/'post_midterm/incremental'/build_id
    if (artifact/'source_registry.json').exists() and read(artifact/'source_registry.json')!=registry:raise ValidationError('IMMUTABLE_REGISTRY_COLLISION')
    if not (artifact/'source_registry.json').exists():write(artifact/'source_registry.json',registry)
    comparison=delta(before.domain,snapshot.domain)
    report={'status':'CANDIDATE_IMPORTED','snapshot_id':snapshot.id,'build_id':build_id,'activated':False,
        'parent_snapshot_id':before.id,'base_snapshot_id':base.id,'source_registry_hash':registry_hash,'idempotent_reuse':unchanged,
        'registry_path':str((artifact/'source_registry.json').relative_to(ROOT)),'requested_removals':removed_pages,
        'source_changes':result['changes'],'graph_delta':comparison,'roundtrip':roundtrip,
        'component_status':result.get('component_status',[]),
        'counts':{k:len(v) for k,v in snapshot.domain.items()},'normalization_issues':normalized['issues'],
        'unchanged_frozen_files':{name:file_hash(ROOT/name)==checksum for name,checksum in frozen.items()},
        'human_review':'PENDING','limitations':[result['source_layers']['limitation'],'New source inputs and old aggregate remain candidate knowledge.']}
    if not all(report['unchanged_frozen_files'].values()):raise ValidationError('FROZEN_INPUT_CHANGED')
    write(artifact/'reports'/(digest(report)+'.json'),report)
    if not (artifact/'result.json').exists():write(artifact/'result.json',report)
    if not (artifact/'normalization.json').exists():write(artifact/'normalization.json',migration)
    print({'status':report['status'],'snapshot_id':snapshot.id,'build_id':build_id,'artifact':str(artifact.relative_to(ROOT)),
        'counts':report['counts'],'delta_counts':{k:{op:len(ids) for op,ids in v.items()} for k,v in comparison.items() if k!='derived'},'derived':comparison['derived']},flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--base-snapshot',required=True);parser.add_argument('--registry');parser.add_argument('--document',action='append',default=[])
    parser.add_argument('--remove-page',action='append',default=[]);parser.add_argument('--label',default='post-midterm-integrated')
    args=parser.parse_args()
    if not args.label or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in args.label):raise ValidationError('BAD_LABEL')
    run(args.base_snapshot,args.registry,args.document,args.remove_page,args.label)
