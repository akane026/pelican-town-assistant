"""Actual Wiki compound asset -> pixel objects -> bounded domain alignment."""
from stardew_agent.core import *
from stardew_agent.parsing import parse_page,extract_structural
from stardew_agent.visual import extract_visual,align_graph
from stardew_agent.model import ModelClient
from stardew_agent.construction import merge_graphs
from stardew_agent.knowledge import Snapshot,build_snapshot,review_export

s=Snapshot(allow_candidate=True);assets=read(DATA/'manifests/assets.json');source=next(x for x in read(DATA/'manifests/sources.json') if x['page_id']=='Bundles')
g=extract_structural(parse_page(source,assets),assets,read(ROOT/'configs/aliases.json'));model=ModelClient();observations=[];regions=[]
target_asset=next(a for a in g['assets'] if a['url'].endswith('/Spring_Crops_Bundle.png'))
for a in g['assets']:
 o,rs=extract_visual(a,model if a['id']==target_asset['id'] else None);observations.append(o);regions+=rs
g['observations']=observations;g['regions']=regions;g['alignments']=align_graph(g,observations,regions)
o=next(x for x in observations if x['asset_id']==target_asset['id']);occ=next(x for x in g['occurrences'] if x['asset_id']==target_asset['id'])
bundle=next(x['target_id'] for x in g['anchors'] if x['occurrence_id']==occ['id'])
relations=[r for r in g['relations'] if r['object']==bundle];ids={r['subject'] for r in relations}|{bundle}
entities=[n for n in g['entities'] if n['id'] in ids];evmap={x['id']:x for x in g['evidence']}
prompt='''Inspect the actual original Wiki compound picture and supplied pixel objects. Map visible regions to ONLY supplied entity or relation IDs. Return {matches:[{region_ids:[],target_kind:"entity" or "relation",target_id,status:"matched" or "ambiguous" or "rejected",evidence_role:"entity_depiction" or "relation_illustration",reason_summary}],unmatched:[],limitations:[]}. A region may support multiple targets; multiple regions may jointly depict one relation. Preserve exact relation direction. Picture can illustrate requirements but cannot prove item quantity, quality, game rules or causal mechanisms. Do not invent IDs. Keep ambiguity when stylized objects are unclear.'''
r=model.structured(prompt,images=[ROOT/target_asset['path']],context={'observation':o,'entities':entities,'relations':relations,'source_quotes':[evmap[i]['quote'] for i in sorted({i for x in relations for i in x['evidence_ids']})]},label='v3_compound_alignment')
accepted=[];rejected=[];region_ids={x['id'] for x in regions if x['asset_id']==target_asset['id']};records={x['id']:x for x in entities+relations}
for x in r.get('parsed',{}).get('matches',[]):
 if x.get('target_id') not in records or not x.get('region_ids') or not set(x['region_ids'])<=region_ids or x.get('target_kind') not in ('entity','relation') or x.get('status') not in ('matched','ambiguous','rejected'):rejected.append(x);continue
 rec=records[x['target_id']];evs=rec.get('evidence_ids') or next(a['evidence_ids'] for a in g['alignments'] if a['target_id']==bundle)
 a={'id':ident('alignment',o['id'],x,r['cache_key']),'page_id':'Bundles','occurrence_id':occ['id'],'region_ids':x['region_ids'],'target_kind':x['target_kind'],'target_id':x['target_id'],
    'evidence_ids':evs,'evidence_role':'relation_illustration' if x['target_kind']=='relation' else 'entity_depiction','support_modes':['pixels','explicit_table_context'],
    'observation_id':o['id'],'method':'compound_mllm_alignment/v1','status':x['status'],'review_status':'candidate','answer_allowed':False,'reason_summary':x.get('reason_summary',''),
    'model_call':{k:r.get(k) for k in ('cache_key','status','execution_mode')}}
 accepted.append(a)
g['alignments']+=accepted
# Replace this page's alignments and occurrences; retained shared records keep their IDs.
base=s.domain.copy();base['alignments']=[a for a in base['alignments'] if a['page_id']!='Bundles'];base['occurrences']=[o for o in base['occurrences'] if o['page_id']!='Bundles']
fused=merge_graphs([base,g]);bid='compound-'+digest(fused)[:16];dest=ARTIFACTS/'builds'/bid
write(dest/'text_graph.json',{k:v for k,v in g.items() if k not in ('observations','regions','alignments')});write(dest/'visual_observation.json',observations);write(dest/'alignment_candidates.json',g['alignments']);write(dest/'fused_graph.json',fused)
manifest={'build_id':bid,'status':'CANDIDATE_BUILT' if r.get('status')=='OK' and o['method']=='ChatECNU_visual/v1' else 'PARTIAL','actual_pixel_objects':len(o['objects']),'new_alignment_candidates':len(accepted),'rejected_schema':rejected,'model_response_status':r.get('status'),'human_review':'PENDING','source_revision':source['revision_id'],'base_snapshot':s.id}
write(dest/'manifest.json',manifest);m=build_snapshot(bid);review_export(m['snapshot_id']);write(DATA/'latest_build.json',{'build_id':bid,'directory':str(dest.relative_to(ROOT))})
write(ARTIFACTS/'evaluation/compound_summary.json',{**manifest,'snapshot_id':m['snapshot_id'],'relation_alignment_candidates':sum(x['target_kind']=='relation' for x in accepted),'semantic_accuracy':'NOT_SCORED_HUMAN_REVIEW_PENDING'})
print(canonical(manifest));print('snapshot',m['snapshot_id']);raise SystemExit(2 if manifest['status']=='PARTIAL' else 0)
