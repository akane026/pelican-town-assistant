"""Hold query, entity inputs and candidate text fixed; vary only query pixels."""
from stardew_agent.core import *
from stardew_agent.knowledge import Snapshot
from stardew_agent.retrieval import Retriever
from stardew_agent.model import ModelClient
s=Snapshot(allow_candidate=True);r=Retriever(s);model=ModelClient();outputs=[]
query='图中这项作物在什么季节生长，首次成熟需要多久？';seeds=['entity:Kale','entity:Garlic']
records={**s.records['facts'],**s.records['relations']}
for method in ('BQ','D'):
    for image_entity in ('Kale','Garlic'):
        asset=next(a for a in s.domain['assets'] if a['url'].endswith('/'+image_entity+'.png'))
        region={'region_id':ident('controlled_query',asset['sha256']),'path':asset['path'],'sha256':asset['sha256']}
        result=r.retrieve(query,entity_ids=seeds,query_regions=[region],rerank_model=model,method=method,candidate=True)
        trace=result['trace'];request=read(ARTIFACTS/'model/requests'/(trace['rerank_trace']['cache_key']+'.json'))
        context=request['context'];fixed={k:context[k] for k in ('question','confirmed_conditions','entity_inputs','candidates','review_status')}
        selected=[{k:records[i][k] for k in ('subject','predicate','value','object') if k in records[i]} for i in trace['selected_ids'][:4]]
        outputs.append({'method':method,'source_icon':image_entity,'query_image_sha256':asset['sha256'],'fixed_text_input_hash':digest(fixed),
                        'selected_top4':selected,'trace':trace,'gold':'PENDING','test_input_kind':'Wiki icon, not independent game screenshot'})
        write(ARTIFACTS/'evaluation/isolated_image_retrieval_rows.json',outputs)
        print(canonical({'method':method,'image':image_entity,'top4':selected}),flush=True)
pairs=[]
for method in ('BQ','D'):
    pair=[x for x in outputs if x['method']==method]
    pairs.append({'method':method,'text_and_entity_inputs_identical':pair[0]['fixed_text_input_hash']==pair[1]['fixed_text_input_hash'],
      'candidate_ids_identical':set(pair[0]['trace']['candidate_ids'])==set(pair[1]['trace']['candidate_ids']),
      'top2_subjects':{x['source_icon']:[r['subject'] for r in x['selected_top4'][:2]] for x in pair}})
summary={'status':'DIAGNOSTIC_EXECUTED','runs':4,'snapshot_id':s.id,'pairs':pairs,'formal_accuracy':None,
         'limits':['Wiki icon interventions, no held-out recognition score.','Different outputs demonstrate sensitivity, not independently established correctness.','Same reranker/conditions/text/explicit entity candidates for BQ and D; underlying graph candidate generation remains each method difference.']}
write(ARTIFACTS/'evaluation/isolated_image_retrieval_summary.json',summary);print(canonical(summary))
raise SystemExit(0 if all(x['text_and_entity_inputs_identical'] and x['candidate_ids_identical'] for x in pairs) else 2)
