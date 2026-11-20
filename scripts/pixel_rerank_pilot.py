"""Actual pixels + question pilot; Wiki inputs are NOT held-out game screenshots."""
from stardew_agent.core import *
from stardew_agent.knowledge import Snapshot
from stardew_agent.retrieval import Retriever
from stardew_agent.model import ModelClient
s=Snapshot(allow_candidate=True);r=Retriever(s);model=ModelClient();rows=[]
cases=[('same_image_growth','Kale','这张图的物品在什么季节生长，需要多久成熟？'),
       ('same_image_processing','Kale','这张图的物品可加工成什么，最终售价公式是什么？'),
       ('same_question_other_image','Garlic','这张图的物品在什么季节生长，需要多久成熟？')]
for case,name,question in cases:
    a=next(x for x in s.domain['assets'] if x['url'].endswith('/'+name+'.png'))
    region={'region_id':ident('diagnostic_roi',a['sha256']),'path':a['path'],'sha256':a['sha256']}
    for method in ('BQ','D'):
        result=r.retrieve(question,entity_ids=['entity:'+name],method=method,candidate=True,query_regions=[region],rerank_model=model)
        row={'case':case,'method':method,'query_image_hash':a['sha256'],'query':question,'explicit_entity_input':name,
             'same_visual_entry_for_bq_d':True,'trace':result['trace'],
             'selected_summary':[{k:x[k] for k in ('id','subject','predicate','object','value') if k in x} for x in result['facts']+result['relations']]}
        rows.append(row);write(ARTIFACTS/'evaluation/pixel_rerank_rows.json',rows)
        print(canonical({'case':case,'method':method,'reranker':result['trace']['reranker'],'mode':result['trace']['execution_mode']}),flush=True)
summary={'status':'DIAGNOSTIC_EXECUTED','runs':len(rows),'snapshot_id':s.id,
 'pixel_rerank_success':sum(x['trace']['reranker']=='chatecnu_question_pixel_rerank/v1' for x in rows),
 'online_requests':sum(x['trace']['budget_used'].get('rerank_model_requests',0) for x in rows),
 'same_image_question_changed_top3':next(x for x in rows if x['case']=='same_image_growth' and x['method']=='D')['trace']['selected_ids'][:3]!=next(x for x in rows if x['case']=='same_image_processing' and x['method']=='D')['trace']['selected_ids'][:3],
 'inputs':'Original Wiki icons with explicit entity inputs, identical across BQ/D. No image recognition accuracy or retrieval gain is inferred.',
 'formal_score':None,'limitations':['No original trained QM.','Single small diagnostic; no independent gold.','Entity input differs in same-question image change; this does not isolate the causal effect of pixels.','Historical 72-run lexical diagnostic remains separate.']}
write(ARTIFACTS/'evaluation/pixel_rerank_summary.json',summary);print(canonical(summary))
raise SystemExit(0 if summary['pixel_rerank_success']==len(rows) else 2)
