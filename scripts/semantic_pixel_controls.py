"""Isolated actual-pixel counterfactuals. Never writes a snapshot or human labels."""
import copy
from stardew_agent.core import *
from stardew_agent.knowledge import Snapshot
from stardew_agent.parsing import parse_page,extract_structural
from stardew_agent.visual import extract_visual,align_graph
from stardew_agent.model import ModelClient

s=Snapshot(allow_candidate=True);before=file_hash(s.directory/'manifest.json');model=ModelClient()
assets=read(DATA/'manifests/assets.json');source=next(x for x in read(DATA/'manifests/sources.json') if x['page_id']=='Kale')
g=extract_structural(parse_page(source,assets),assets,read(ROOT/'configs/aliases.json'))
orig=next(a for a in g['assets'] if a['url'].endswith('/Kale.png'))
swap=next(a for a in s.domain['assets'] if a['url'].endswith('/Garlic.png'))
occ=next(o for o in g['occurrences'] if o['asset_id']==orig['id'] and o['near_text'] and any(a['occurrence_id']==o['id'] and a['target_id']=='entity:Kale' for a in g['anchors']))
anchor=next(a for a in g['anchors'] if a['occurrence_id']==occ['id'] and a['target_id']=='entity:Kale')
base={**g,'assets':[orig],'occurrences':[occ],'anchors':[anchor],'relations':[],
      'entities':[e for e in g['entities'] if e['id']=='entity:Kale']}
obs=next(o for o in s.domain['observations'] if o['asset_id']==orig['id'] and o['method']=='ChatECNU_visual/v1')
regions=[r for r in s.domain['regions'] if r['asset_id']==orig['id']]
swap_obs,swap_regions=extract_visual(swap,model)
out=[]
for variant in ('original','swapped_pixels','missing_pixels','no_context'):
    candidate=copy.deepcopy(base);observations=[obs];rs=regions
    if variant=='swapped_pixels':
        candidate['assets']=[swap];candidate['occurrences'][0]['asset_id']=swap['id'];observations=[swap_obs];rs=swap_regions
    elif variant=='missing_pixels':observations=[];rs=[]
    elif variant=='no_context':candidate['occurrences'][0]['near_text']=''
    result=align_graph(candidate,observations,rs,model)
    out.append({'variant':variant,'context_characters':len(candidate['occurrences'][0]['near_text']),'intentionally_modified_isolated_copy':variant!='original','actual_image_sha256':candidate['assets'][0]['sha256'] if observations else None,
                'observation_mode':observations[0]['method'] if observations else None,'alignments':result,'model_call':candidate.get('alignment_model_log'),
                'gold_review':'PENDING','evaluation_scope':'single Wiki icon diagnostic, not independent screenshot accuracy'})
    write(ARTIFACTS/'evaluation/semantic_pixel_controls_rows.json',out)
    print(canonical({'variant':variant,'statuses':[a['status'] for a in result],'call':candidate.get('alignment_model_log')}),flush=True)
status_by={x['variant']:[a['status'] for a in x['alignments']] for x in out}
summary={'status':'DIAGNOSTIC_EXECUTED','protocol_version':'nonempty_context_v2','snapshot_id':s.id,'snapshot_unchanged':before==file_hash(s.directory/'manifest.json'),
 'statuses':status_by,'missing_pixels_produced_no_alignment':not status_by['missing_pixels'],
 'swapped_pixels_flagged':any(v in ('conflicting','rejected','ambiguous','unmatched') for v in status_by['swapped_pixels']),
 'original_observation_reused':True,'new_alignment_requests':[x.get('model_call') for x in out],
 'context_actually_removed':out[0]['context_characters']>0 and out[3]['context_characters']==0,
 'semantic_accuracy':'NOT_SCORED_HUMAN_REVIEW_PENDING','limitation':'One source-context intervention. Candidate identity remains available without near_text; this is not a text-free recognition test.'}
write(ARTIFACTS/'evaluation/semantic_pixel_controls_summary.json',summary);print(canonical(summary))
raise SystemExit(0 if summary['snapshot_unchanged'] and summary['swapped_pixels_flagged'] and summary['missing_pixels_produced_no_alignment'] else 2)
