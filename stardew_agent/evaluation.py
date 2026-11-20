"""Bounded, reproducible engineering diagnostics; never a substitute for human gold."""
from __future__ import annotations
import copy,resource,time,statistics
from collections import Counter
from .core import *
from .knowledge import Snapshot
from .retrieval import Retriever
from .rules import dependencies,missing_dependencies
from .evidence import BundleStore
from .calculations import execute

CASES=[
 ('new_crop_sale','12个普通甘蓝直接卖多少钱','sale_value',{'entity_id':'entity:Kale','quantity':12,'quality':'normal','profession':'none'}),
 ('seed_growth','春23日种防风草种子何时成熟','growth_timing',{'entity_id':'entity:Parsnip_Seeds','day':23,'season':'Spring','watered':True,'acceleration':'none'}),
 ('new_crop_growth','春24日种大蒜是否来得及收获','growth_timing',{'entity_id':'entity:Garlic','day':24,'season':'Spring','watered':True,'acceleration':'none'}),
 ('new_crop_summer','夏18日种番茄何时成熟','growth_timing',{'entity_id':'entity:Tomato','day':18,'season':'Summer','watered':True,'acceleration':'none'}),
 ('fruit_processing','2个金星甜瓜做果酒与直接卖比较','processing_value',{'entity_id':'entity:Melon','product_id':'entity:Wine','quantity':2,'quality':'gold','profession':'none'}),
 ('vegetable_processing','5个普通防风草做腌菜比较价值','processing_value',{'entity_id':'entity:Parsnip','product_id':'entity:Pickles','quantity':5,'quality':'normal','profession':'none'}),
 ('keg_materials','制作2个小桶缺哪些材料','crafting_gap',{'entity_id':'entity:Keg','quantity':2,'inventory':{},'user_level':8}),
 ('jar_materials','制作3个罐头瓶缺哪些材料','crafting_gap',{'entity_id':'entity:Preserves_Jar','quantity':3,'inventory':{},'user_level':4}),
 ('spring_reserve','春季作物收集包预留库存','bundle_reserve',{'entity_id':'entity:Spring_Crops_Bundle','inventory':{x:{'normal':10} for x in ('Parsnip','Green_Bean','Cauliflower','Potato')},'completed':[]}),
 ('quality_choice','高品质作物收集包三选哪些库存','bundle_reserve',{'entity_id':'entity:Quality_Crops_Bundle','inventory':{x:{'gold':5} for x in ('Parsnip','Melon','Pumpkin','Corn')},'completed':[]}),
 ('stage_interval','甘蓝第2生长阶段还剩多少天','stage_remaining',{'entity_id':'entity:Kale','stage':2,'watered':True,'acceleration':'none'}),
 ('same_entity_different_goal','甘蓝做腌菜价值','processing_value',{'entity_id':'entity:Kale','product_id':'entity:Pickles','quantity':3,'quality':'normal','profession':'none'})]

def retrieval_diagnostic(protocol):
    s=Snapshot(allow_candidate=True);r=Retriever(s);store=BundleStore();outputs=[];start=time.perf_counter()
    frozen={'snapshot_id':s.id,'cases':[{'id':i,'query':q,'rule':rule,'params':p} for i,q,rule,p in CASES],'protocol':protocol,
            'reference_type':'rule dependency coverage, not independently annotated semantic accuracy','image_input':'identical explicit entity IDs for all methods; no new image recognition score',
            'supplement_rounds':2,'initial_and_supplement_separate':True}
    freeze=ARTIFACTS/'evaluation/retrieval_protocol.json'
    if freeze.exists() and read(freeze)!=frozen:freeze=ARTIFACTS/'evaluation'/('retrieval_protocol-'+digest(frozen)[:10]+'.json')
    write(freeze,frozen)
    for cid,q,rule,params in CASES:
        for method in protocol['retrieval']:
            task=f'eval:{cid}:{method}';begin=time.perf_counter()
            out=r.retrieve(q,entity_ids=[params['entity_id']],method=method,candidate=True,task_id=task)
            b=store.get(out['bundle_id'],task_id=task,revision=0,snapshot_id=s.id);dep=dependencies(rule,params,b.data());missing=missing_dependencies(b.data(),dep['selectors'])
            initial_complete=not missing and not dep.get('dependency_discovery_incomplete',False);initial_result=execute(rule,b,params);supp=[]
            for _ in range(2):
                dep=dependencies(rule,params,b.data());missing=missing_dependencies(b.data(),dep['selectors'])
                if not missing:break
                added=r.supplement(b,missing,candidate=True);supp.append(added['trace']);b=store.get(added['bundle_id'],task_id=task,revision=0,snapshot_id=s.id)
            result=execute(rule,b,params)
            outputs.append({'case_id':cid,'method':method,'query':q,'initial_complete':initial_complete,'initial_trace':out['trace'],
                'initial_result':initial_result,'supplement_traces':supp,'application_result':result,'application_calculated':bool(result.get('run_id')),
                'latency_seconds':time.perf_counter()-begin,'source_snapshot':s.id,'formal_success':None})
    groups={m:{'cases':len(CASES),'initial_dependency_complete':sum(x['initial_complete'] for x in outputs if x['method']==m),
               'after_explicit_supplement_calculated':sum(x['application_calculated'] for x in outputs if x['method']==m),
               'mean_seconds':statistics.mean(x['latency_seconds'] for x in outputs if x['method']==m)} for m in protocol['retrieval']}
    paired=[]
    for cid,*_ in CASES:
        b=next(x for x in outputs if x['case_id']==cid and x['method']=='BQ');d=next(x for x in outputs if x['case_id']==cid and x['method']=='D')
        paired.append({'case_id':cid,'initial':'D_WIN' if d['initial_complete']>b['initial_complete'] else 'BQ_WIN' if b['initial_complete']>d['initial_complete'] else 'TIE',
            'BQ_selected':b['initial_trace']['selected_ids'],'D_selected':d['initial_trace']['selected_ids']})
    summary={'status':'PASS_ENGINEERING_DIAGNOSTIC','formal_evaluation':'BLOCKED_HUMAN_GOLD_PENDING','snapshot_id':s.id,'groups':groups,
        'BQ_D_initial_pairs':dict(Counter(x['initial'] for x in paired)),'total_seconds':time.perf_counter()-start,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'limits':['12 development diagnostics, not blind questions.','This protocol disables online reranking: same lexical scorer for BQ and D. Actual pixel reranking is a separately recorded pilot.','No semantic task-success claim.','A/A+ use fact records as textual chunks, not a separately embedded full-text baseline.']}
    write(ARTIFACTS/'evaluation/retrieval_rows.json',outputs);write(ARTIFACTS/'evaluation/retrieval_pairs.json',paired);write(ARTIFACTS/'evaluation/retrieval_summary.json',summary)
    return summary

def construction_diagnostic(protocol):
    s=Snapshot(allow_candidate=True);align=s.domain['alignments'];observ=s.domain['observations'];sources=read(DATA/'manifests/sources.json')
    # All source image occurrences are sampled before looking at prediction outcomes.
    from .parsing import parse_page
    units=[]
    for source in sources:
        b=parse_page(source,read(DATA/'manifests/assets.json'))
        for o in b['occurrences']:
            if o['asset_id']:units.append({'unit_id':o['id'],'page':source['page_id'],'source_revision':source['revision_id'],'asset_id':o['asset_id'],'locator':o['locator'],
                'context':o['near_text'],'expected_targets':None,'expected_roles':None,'human_review':'PENDING','sample_origin':'source_DOM_occurrences_not_prediction_list'})
    # Ablation freezes all text facts and relations; K0 removes only semantic pixel decisions.
    k0=[{**a,'status':'matched','method':'structural_only_ablation','observation_id':None} for a in align if a['method'] not in ('compound_mllm_alignment/v1',)]
    k1=copy.deepcopy(align)
    controls=[]
    from .visual import pixel_observation
    for a in s.domain['assets'][:2]:
        o,_=pixel_observation(a);controls.append({'asset_id':a['id'],'input_image_sha256':o['input_image_sha256'],'pixel_statistics':o['pixel_statistics']})
    changes=[{'id':a['id'],'target_id':a['target_id'],'kind':a['target_kind'],'role':a['evidence_role'],'status':a['status'],'reason':a['reason_summary']} for a in align if a['method'] in ('mllm_alignment/v1','compound_mllm_alignment/v1')]
    summary={'status':'PARTIAL','snapshot_id':s.id,'fixed_text_graph_hash':digest([s.domain['entities'],s.domain['facts'],s.domain['relations']]),
      'source_pages':len(sources),'independent_assets':len(s.domain['assets']),'source_units_for_review':len(units),'alignment_methods':dict(Counter(a['method'] for a in align)),
      'pixel_observation_methods':dict(Counter(o['method'] for o in observ)),'K0_candidate_count':len(k0),'K1_candidate_count':len(k1),
      'K1_model_alignment_statuses':dict(Counter(a['status'] for a in changes)),'relation_roles':dict(Counter(a['evidence_role'] for a in align if a['target_kind']=='relation')),
      'accuracy':None,'human_gold':'PENDING','limits':['K0/K1 use identical text facts; this is a structural versus pixel-decision ablation, not a separate full training run.',
          'Source units are review tasks, not assistant-approved labels.','Missing/swap/context cache isolation tested; semantic counterfactual model evaluation remains incomplete.','Most mappings use DOM context plus pixel validation, not independent MLLM recognition.']}
    write(ARTIFACTS/'evaluation/construction_source_units.json',units);write(ARTIFACTS/'evaluation/construction_K0.json',k0);write(ARTIFACTS/'evaluation/construction_K1.json',k1)
    write(ARTIFACTS/'evaluation/construction_cases.json',changes);write(ARTIFACTS/'evaluation/pixel_controls.json',controls);write(ARTIFACTS/'evaluation/construction_summary.json',summary)
    return summary

def evaluate(suite,protocol,online=False):
    if suite=='retrieval':return retrieval_diagnostic(protocol)
    if suite=='construction':return construction_diagnostic(protocol)
    if suite=='agent':
        runs=[]
        for p in (ARTIFACTS/'agent_pilots').glob('*.json'):
            d=read(p);a=d.get('answer',d)
            if isinstance(a,dict):runs.append({'path':str(p.relative_to(ROOT)),'status':a.get('status'),'tool_calls':len(a.get('tool_events',[])),'calculation_count':len(a.get('calculation_traces',[])),'mode':'saved_real_online_run'})
        result={'status':'PARTIAL','mode':'summarize_existing_online_runs_no_replay_as_new_execution','runs':runs,'formal_gold':'PENDING'}
        write(ARTIFACTS/'evaluation/agent_summary.json',result);return result
    if suite=='formal' and (ARTIFACTS/'evaluation/formal_summary.json').exists():
        return {**read(ARTIFACTS/'evaluation/formal_summary.json'),'status':'BLOCKED','mode':'prepared_dataset_summary_not_formal_execution'}
    if suite=='reliability' and (ARTIFACTS/'evaluation/reliability_summary.json').exists():
        return {**read(ARTIFACTS/'evaluation/reliability_summary.json'),'mode':'summarize_recorded_tests_not_new_execution'}
    return {'status':'BLOCKED','suite':suite,'reason':'Formal gold / independent visual holdout / complete reliability suite not finished. Use pytest for implemented engineering tests.','online_requested':online,'model_calls':0}
