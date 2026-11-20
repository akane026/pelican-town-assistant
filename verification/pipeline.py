"""Executable screenshot -> candidates -> evidence -> deterministic tool pipeline."""
from __future__ import annotations
from .common import BASE, DATA, dump, load, read_jsonl
from .graph import GRAPH, KnowledgeGraph, EvidenceError
from .vision import VisualRetriever
from .retrieval import Retriever
from .calculators import EvidenceResolver, TaskError, stage_remaining, stage_date_consistent


class AssistantPipeline:
    def __init__(self,directory=GRAPH,index_snapshot=None):
        self.directory=directory;self.index_snapshot=index_snapshot;self.vision=VisualRetriever()

    def run(self,request):
        trace={'request':request,'mode':'verification_only','production_dependency_completion':[],
               'notice':'Explicit intent/state, no full-screen detection/OCR. Frozen Wiki version not release-validated.'}
        try:
            graph=KnowledgeGraph(self.directory,expected_snapshot=self.index_snapshot)
            if request.get('image_sha256'):
                from .common import file_sha
                if file_sha(BASE/request['image_path'])!=request['image_sha256']:raise TaskError('TOOL_ERROR','image checksum mismatch')
            prediction=self.vision.candidates(BASE/request['image_path'],request['kind']);trace['visual']=prediction
            if request.get('reject_all_candidates'):raise TaskError('UNKNOWN','请提供更清晰的截图或手动选择物品。')
            entity=request.get('confirmed_entity')
            if request['kind']=='stage' and not entity:
                raise TaskError('NEEDS_CONFIRMATION','幼苗外观可能相似，请确认阶段后再计算区间。')
            if entity:
                if entity not in {c['entity'] for c in prediction['candidates']}:raise TaskError('INVALID_INPUT','confirmation outside candidate set')
                trace['assistance']='scripted_confirmation'
            elif prediction['status']=='AUTO_ACCEPT':entity=prediction['candidates'][0]['entity'];trace['assistance']='none'
            else:raise TaskError('NEEDS_CONFIRMATION','请确认候选；相似度不是正确概率。')
            trace['entity']=entity
            retrieval=Retriever(graph).retrieve({'query_id':'runtime','question':request['question'],
                'visual_entities':[entity],'identification_mode':trace['assistance'],'player_state':request.get('state',{})})
            trace['retrieval']=retrieval['methods']['D'];state=request.get('state',{})
            if request['intent']=='planting':
                if not entity.endswith('_Seeds'):raise TaskError('NEEDS_INPUT','请选择种子，或确认需要种植的作物。')
                resolver=EvidenceResolver(graph)
                calculation=resolver.planting(entity,day=state.get('day'),plants=state.get('plants'),season=state.get('season'),
                    watered=state.get('watered'),acceleration=state.get('acceleration','none'),quality=state.get('quality','normal'))
                facts=resolver.used;result=calculation['result'];trace['calculation']=calculation
                if result['status']=='NO_HARVEST':answer='按当前季节和种植日期，本季无法成熟。'
                else:answer=f"在每天浇水、无加速、普通品质的前提下，于第 {result['harvest_days'][0]} 天成熟；种子成本 {result['seed_cost_g']}g，销售额 {result['sales_g']}g，仅扣种子成本的收益 {result['margin_after_seed_g']}g。"
            elif request['intent']=='remaining':
                metadata=graph.nodes[entity]['metadata']
                if 'stage' not in metadata:raise TaskError('NEEDS_INPUT','请选择具体生长阶段。')
                if state.get('watered') is not True:raise TaskError('NEEDS_INPUT','需要确认每天浇水。')
                if state.get('acceleration','none')!='none':raise TaskError('UNSUPPORTED_CONDITIONS','加速条件未覆盖。')
                duration=graph.fact(metadata['crop'],'stage_durations');water=graph.fact('Calendar','watered_growth')
                if state.get('planted_day') is not None and state.get('day') is not None:
                    stage_date_consistent(duration['value'],metadata['stage'],state['day']-state['planted_day'])
                remaining=stage_remaining(duration['value'],metadata['stage']);facts=[duration,water]
                result={'remaining_growth_nights':remaining,'stage':metadata['stage']}
                trace['calculation']={'result':result,'rule_id':'stage_interval/v1','snapshot_id':graph.manifest['snapshot_id'],
                                      'input_facts':facts,'user_inputs':state}
                answer=f"按当前阶段、每天浇水且无加速计算，还需 {remaining[0]}—{remaining[1]} 个有效生长夜晚；截图不能确定在本阶段已停留多久。"
            else:raise TaskError('UNSUPPORTED_CONDITIONS','intent outside verified two-chain scope')
            # Runtime may explicitly complete tool dependencies. Controlled A-D does not do this.
            retrieved=set(trace['retrieval']['final_ids'])
            trace['production_dependency_completion']=[{'fact_id':f['id'],'pages':[e['page_id'] for e in f['evidence']]} for f in facts if f['id'] not in retrieved]
            if len(facts)>12:raise TaskError('TOOL_ERROR','dependency completion limit exceeded')
            return {'status':'OK','answer':answer,'result':result,'evidence_ids':[f['id'] for f in facts],
                    'citations':sorted({e['url'] for f in facts for e in f['evidence']}),'trace':trace}
        except TaskError as exc:return {'status':exc.status,'detail':exc.detail,'trace':trace}
        except EvidenceError as exc:
            return {'status':'STALE_INDEX' if 'STALE_INDEX' in str(exc) else 'INCOMPLETE_EVIDENCE','detail':str(exc),'trace':trace}
        except (OSError,ValueError,KeyError) as exc:return {'status':'TOOL_ERROR','detail':type(exc).__name__,'trace':trace}


def probe():
    samples={r['sample_id']:r for r in read_jsonl(DATA/'visual_test_manifest.jsonl')}
    def req(sample,intent,**state):
        s=samples[sample]
        return {'image_path':s['path'],'image_sha256':s['sha256'],'kind':s['kind'],'intent':intent,
                'question':'这些种子春季种下多久成熟、收益多少？' if intent=='planting' else '这个作物阶段还需要多久成熟？',
                'state':{'watered':True,'acceleration':'none',**state}}
    seed=req('V28','planting',day=23,plants=50,season='Spring')
    stage={**req('V33','remaining'),'confirmed_entity':'Melon_Stage_3'};pipeline=AssistantPipeline();cases=[]
    def case(id,request,expected,validator=None,engine=None,recovery=None):
        result=(engine or pipeline).run(request);passed=result['status']==expected and (validator(result) if validator else True)
        recovered=recovery() if recovery else None
        if recovered is not None:passed=passed and recovered['status']=='OK'
        record={'case_id':id,'expected_status':expected,'passed':passed,'output':result,'recovery':recovered}
        cases.append(record);dump(BASE/'artifacts/e2e'/(id+'.json'),record)
    case('E01_seed_profit',seed,'OK',lambda r:r['result']['harvest_days']==[27] and r['result']['margin_after_seed_g']==750)
    case('E02_stage_interval',stage,'OK',lambda r:r['result']['remaining_growth_nights']==[7,9])
    case('E03_unknown', {**req('V18','planting',day=23,plants=50,season='Spring'),'reject_all_candidates':True},'UNKNOWN',
         recovery=lambda:pipeline.run(seed))
    case('E04_ambiguous',req('V32','remaining'),'NEEDS_CONFIRMATION',
         recovery=lambda:pipeline.run({**req('V32','remaining'),'confirmed_entity':'Melon_Stage_6'}))
    case('E05_missing_input',req('V28','planting',day=23,season='Spring'),'NEEDS_INPUT',recovery=lambda:pipeline.run(seed))
    case('E06_conflict',{**req('V33','remaining',planted_day=1,day=3),'confirmed_entity':'Melon_Stage_3'},'CONFLICT',
         recovery=lambda:pipeline.run({**req('V33','remaining',planted_day=1,day=5),'confirmed_entity':'Melon_Stage_3'}))
    missing=AssistantPipeline(BASE/'artifacts/interventions/missing_unique_source')
    case('E07_missing_evidence',seed,'INCOMPLETE_EVIDENCE',engine=missing,recovery=lambda:pipeline.run(seed))
    changed=BASE/'artifacts/interventions/related_price'
    stale=AssistantPipeline(changed,index_snapshot=load(GRAPH/'manifest.json')['snapshot_id'])
    case('E08_stale_index',seed,'STALE_INDEX',engine=stale,
         recovery=lambda:AssistantPipeline(changed,index_snapshot=load(changed/'manifest.json')['snapshot_id']).run(seed))
    result={'status':'PASS_DIAGNOSTIC' if all(c['passed'] for c in cases) else 'FAIL','cases':8,'passed':sum(c['passed'] for c in cases),
        'results':[{k:c[k] for k in ['case_id','passed','expected_status']} for c in cases],
        'scope':'two real cropped-image chains + six negative scenarios; scripted user clarification; template output',
        'limitations':['unknown case includes scripted rejection','all stages require scripted user confirmation','stage sample count below plan','game version unverified','no live user study','production dependency completion is outside controlled D']}
    dump(BASE/'results/v07.json',result);print(result);return int(result['status']=='FAIL')

if __name__=='__main__':raise SystemExit(probe())
