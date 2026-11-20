"""Recover real archived document/component lineage, never invent page slices."""
from __future__ import annotations
import copy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stardew_agent.core import ROOT,DATA,ARTIFACTS,read,write,file_hash,digest,ident,relation,validate_graph,ValidationError
from stardew_agent.parsing import entity_id
from stardew_agent.construction import legacy_rules,merge_graphs,reconcile_sources,reconcile_contribution_registry
from stardew_agent.normalization import normalize_graph,DEFAULT_POLICY
from stardew_agent.knowledge import Snapshot,build_snapshot,validate_region_files
from stardew_agent.knowledge_quality import audit_graph
from stardew_agent.capabilities import GROUPS
from post_midterm_integrate import delta

BASE='c704b0819193e793a6f5088b3d2dac57363698cd687bb74e5eb6ae3e8cddf303'
BATCHES=['6f54ce74ede3f8efd62b','2690cb1f40265ba01efb','c58179dbb893a7d6ebb6']
OUT=ARTIFACTS/'post_midterm/source_recovery'


def provenance(path):return {'path':str(path.relative_to(ROOT)),'file_sha256':file_hash(path)}
def empty():return {k:[] for k in GROUPS}


def recover():
    base=Snapshot(BASE,allow_candidate=True);original=Snapshot(base.manifest['parent_snapshot_id'],allow_candidate=True)
    documents=[];lineage={};archived_files=[]
    for batch in BATCHES:
        directory=ARTIFACTS/'builds'/batch;manifest=read(directory/'manifest.json')
        archived_files.append(provenance(directory/'manifest.json'))
        for page in [r['page_id'] for r in manifest['sources']]:
            path=directory/'documents'/page/'fused_document_graph.json';doc=read(path)
            if doc['page_id']!=page:raise ValidationError('ARCHIVED_PAGE_MISMATCH')
            documents.append(doc);lineage[page]={'kind':'archived_original_document','inputs':[provenance(path)]};archived_files.append(provenance(path))
    if len(documents)!=24 or len({d['page_id'] for d in documents})!=24:raise ValidationError('EXPECTED_24_ORIGINAL_DOCUMENTS')
    # The original compound build explicitly replaced Bundles occurrences and
    # alignments while retaining its other prior source contributions.
    compound=ARTIFACTS/'builds/compound-1cd3a091e8abbbce';text_path=compound/'text_graph.json'
    observed_path=compound/'visual_observation.json';alignment_path=compound/'alignment_candidates.json';full_path=compound/'fused_graph.json'
    text=read(text_path);observations=read(observed_path);alignments=read(alignment_path);full=read(full_path)
    required_regions={o['region_id'] for ob in observations for o in ob['objects']}|{r for a in alignments for r in a['region_ids']}
    required_regions|={ident('region',a['id'],[0,0,1,1],'whole-v1') for a in text['assets']}
    region_index={r['id']:r for r in full['regions']}
    if required_regions-region_index.keys():raise ValidationError('ARCHIVED_REGION_METADATA_MISSING')
    reconstructed={**text,'observations':observations,'alignments':alignments,'regions':[region_index[r] for r in sorted(required_regions)]}
    validate_graph(reconstructed);validate_region_files(reconstructed)
    old=next(d for d in documents if d['page_id']=='Bundles');old=copy.deepcopy(old);old['occurrences']=[];old['alignments']=[]
    template_path=ARTIFACTS/'builds/bundle-template-225d6ccec441f5/fused_graph.json';template=read(template_path);template['occurrences']=[];template['alignments']=[]
    bundles={**text,**merge_graphs([old,template,reconstructed])}
    inputs=[*lineage['Bundles']['inputs'],*[provenance(p) for p in (template_path,text_path,observed_path,alignment_path,full_path)]]
    bundles['recovery']={'kind':'reconstructed_from_original_component_artifacts','inputs':inputs,
        'region_metadata_lookup':'Only IDs explicitly referenced by archived objects/alignments and the deterministic whole-image region contract.',
        'not_claimed':'This is not an original serialized fused-document file or an arbitrary snapshot page slice.'}
    documents=[bundles if d['page_id']=='Bundles' else d for d in documents];lineage['Bundles']=bundles['recovery']
    archived_files+=inputs[1:]
    canonical=reconcile_sources([],documents)['documents']
    source_facts=merge_graphs(canonical)['facts'];legacy=legacy_rules();legacy_input=ROOT/'verification/data/graph_input.json'
    raw=read(legacy_input);old_facts={n['metadata']['id']:n['metadata'] for n in raw['entities'] if n['type']=='Fact'}
    current_by_old={old:f for f in legacy['facts'] for old in f.get('legacy_ids',[])}
    unresolved=[]
    def resolve(old_id):
        if old_id in current_by_old:return current_by_old[old_id]
        old=old_facts.get(old_id)
        matches=[f for f in source_facts if old and f['subject']==entity_id(old['subject']) and f['predicate']==old['predicate'] and f['value']==old['value'] and f['unit']==old['unit']]
        unique={f['id']:f for f in matches}
        if len(unique)==1:return next(iter(unique.values()))
        unresolved.append({'legacy_fact_id':old_id,'candidate_ids':sorted(unique)});return None
    entities={e['id']:e for g in [legacy,*canonical] for e in g['entities']}
    evidence={e['id']:e for g in [legacy,*canonical] for e in g['evidence']}
    components=[]
    def component(kind,row,record_group,source_metadata):
        graph=empty();graph[record_group]=[row]
        graph['evidence']=[evidence[i] for i in row['evidence_ids']]
        entity_ids={row['subject']}|({row['object']} if record_group=='relations' else set())
        graph['entities']=[entities[i] for i in sorted(entity_ids)]
        validate_graph(graph)
        return {'id':kind+':'+row['id'],'kind':kind,'graph':graph,
            'source_bindings':[{'page_id':p,'source_id':s} for p,s in sorted({(e['page_id'],e['source_id']) for e in graph['evidence']})],
            'lineage':{'legacy_input':provenance(legacy_input),'metadata':source_metadata,'method':'recover_explicit_original_fact_id_dependencies'}}
    for fact in legacy['facts']:components.append(component('legacy_fact',copy.deepcopy(fact),'facts',{'legacy_ids':fact['legacy_ids']}))
    original_relations={}
    for row in raw['relationships']:
        if row.get('metadata',{}).get('fact_id') not in current_by_old or row['type'] in ('HAS_FACT','SUPPORTED_BY'):continue
        rid=relation(entity_id(row['source']),row['type'],entity_id(row['target']),[])['id'];original_relations[rid]=row
    for relation_row in legacy['relations']:
        row=copy.deepcopy(relation_row);archived=original_relations[row['id']];metadata=archived['metadata']
        old_ids=metadata.get('support_fact_ids') or [metadata['fact_id']]
        supports=[resolve(i) for i in old_ids];row['support_fact_ids']=[f['id'] for f in supports if f]
        row['legacy_dependency_metadata']=metadata;row['dependency_contract']='v1'
        if any(f is None for f in supports):row['derivation_inputs_incomplete']=True
        row['evidence_ids']=list(dict.fromkeys(row['evidence_ids']+[e for f in supports if f for e in f['evidence_ids']]))
        components.append(component('legacy_relation',row,'relations',{'original_relation_id':archived['id'],**metadata}))
    result=reconcile_contribution_registry(canonical,[],components=components)
    normalized=normalize_graph(result['graph']);graph=normalized['graph']
    # Coverage is measured against real original aggregate records, excluding
    # recomputed derivations. Metadata improvements are reported, not hidden.
    coverage={}
    for group in GROUPS:
        old={r['id'] for r in original.domain[group] if r.get('method') not in ('source_grounded_category_join','stage_sequence_illustration/v1')}
        new={r['id'] for r in result['graph'][group] if r.get('method') not in ('source_grounded_category_join','stage_sequence_illustration/v1')}
        coverage[group]={'original':len(old),'recovered':len(new),'missing_ids':sorted(old-new),'additional_ids':sorted(new-old)}
    if any(coverage[k]['missing_ids'] for k in GROUPS):
        write(OUT/'coverage_failure.json',coverage);raise ValidationError('RECOVERY_MISSING_ORIGINAL_RECORDS')
    descriptors=[]
    for document in result['documents']:
        checksum=digest(document);path=DATA/'post_midterm/source_contributions'/document['page_id']/(checksum+'.json');write(path,document)
        source=document['source'];descriptors.append({'page_id':document['page_id'],'source_id':document['source_id'],
            'document_hash':checksum,'path':str(path.relative_to(ROOT)),'file_sha256':file_hash(path),'source_sha256':source['sha256'],
            'raw_path':source['raw_path'],'revision_id':source['revision_id'],'capture_kind':source.get('capture_kind','historical_source_manifest'),'lineage':lineage[document['page_id']]})
    component_descriptors=[]
    for c in components:
        path=DATA/'post_midterm/source_components'/(digest(c)+'.json');write(path,c)
        component_descriptors.append({'id':c['id'],'kind':c['kind'],'path':str(path.relative_to(ROOT)),'file_sha256':file_hash(path),'source_bindings':c['source_bindings']})
    identity={'schema':'source-contribution-registry/v2','base_snapshot_id':base.id,'base_graph_content_hash':base.manifest['graph_content_hash'],
        'base_layer_kind':'recovered_source_components','documents':descriptors,'components':component_descriptors,
        'component_status':result['component_status'],'policy_hash':digest(DEFAULT_POLICY),'replaceable_page_ids':[d['page_id'] for d in result['documents']],'aggregate_page_ids':[]}
    registry_hash=digest(identity);build_id='post-midterm-recovered-'+digest({'registry_hash':registry_hash,'graph':graph})[:20]
    directory=ARTIFACTS/'builds'/build_id;write(directory/'fused_graph.json',graph)
    migration={**normalized['migration'],'parent_snapshot_id':base.id,'source_registry_hash':registry_hash,'recovery_kind':'real_archived_documents_and_explicit_components'}
    manifest=build_snapshot(build_id,activate=False,migration=migration);snapshot=Snapshot(manifest['snapshot_id'],allow_candidate=True)
    registry={'identity':identity,'registry_hash':registry_hash,'snapshot_id':snapshot.id,'build_id':build_id,
        'limitation':result['source_layers']['limitation']}
    write(OUT/'source_registry.json',registry)
    report={'status':'RECOVERED_CANDIDATE','snapshot_id':snapshot.id,'build_id':build_id,'source_registry_hash':registry_hash,
        'original_document_pages':24,'component_reconstructed_pages':['Bundles'],'legacy_components':len(components),'unresolved_legacy_dependencies':unresolved,
        'record_id_coverage':coverage,'graph_delta_from_normalized_base':delta(base.domain,graph),'archived_inputs':archived_files,
        'quality':audit_graph(graph),'roundtrip':snapshot.roundtrip(),'human_review':'PENDING','activated':False,
        'limitations':['Bundles page contribution is transparently reconstructed from original component artifacts.','Changed legacy source bindings retract only affected fact/relation components until new extraction.']}
    write(OUT/'result.json',report)
    print({'status':report['status'],'snapshot_id':snapshot.id,'build_id':build_id,'documents':len(descriptors),'components':len(components),
           'counts':{k:len(graph[k]) for k in GROUPS},'missing_original_ids':sum(len(v['missing_ids']) for v in coverage.values()),'unresolved_dependencies':unresolved})
    return report


if __name__=='__main__':recover()
