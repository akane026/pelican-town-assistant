"""Pure evidence-bound calculations: deliberately no knowledge/retrieval imports."""
from itertools import combinations
from .core import ValidationError,ident,canonical
from .rules import RULES,dependencies,missing_dependencies,rule_audit,rule_fingerprint,matches_selector
from .evidence import VerifiedBundle
from verification.calculators import process_value,crafting,stage_remaining,integer

QUALITY={'normal':0,'silver':1,'gold':2,'iridium':3}
def execute(rule_id,bundle:VerifiedBundle,params,*,formal=False):
    body=bundle.data();dep=dependencies(rule_id,params,body);missing=missing_dependencies(body,dep['selectors'])
    if dep['missing_inputs']:return {'status':'NEEDS_INPUT','missing_inputs':dep['missing_inputs']}
    if missing or dep.get('dependency_discovery_incomplete'):return {'status':'INCOMPLETE_EVIDENCE','missing_dependencies':missing or dep['selectors']}
    if formal and (body['execution_mode']!='released' or rule_audit(rule_id)['status']!='approved_human'):return {'status':'BLOCKED','reason':'KNOWLEDGE_OR_RULE_REVIEW_PENDING'}
    if params.get('quality','normal') not in QUALITY:return {'status':'UNSUPPORTED_CONDITIONS','reason':'quality'}
    if params.get('profession','none')!='none':return {'status':'UNSUPPORTED_CONDITIONS','reason':'profession'}
    used=[];relations=[]
    def get(s,p,u):
        values=[f for f in body['facts'] if matches_selector(f,{'subject':s,'predicate':p,'unit':u,'__context':params})]
        if not values:raise ValidationError('MISSING_FACT')
        if len({canonical(f['value']) for f in values})!=1 or any(f['review_status']=='conflicted' for f in values):raise ValidationError('CONFLICTING_FACTS')
        used.extend(values);return values[0]['value']
    for sel in dep['selectors']:
        if sel['kind']=='relation':relations.extend(r for r in body['relations'] if matches_selector(r,sel))
    e=params['entity_id'];steps=[]
    if rule_id=='sale_value':
        q=integer(params['quantity'],'quantity');unit=get(e,'sell_'+params['quality'],'g');out={'unit_value_g':unit,'quantity':q,'sales_g':unit*q};steps=[f'{unit} × {q} = {unit*q} g']
    elif rule_id in ('growth_timing','stage_remaining'):
        if params['watered'] is not True or params['acceleration']!='none':return {'status':'UNSUPPORTED_CONDITIONS','reason':'daily watering and no acceleration required'}
        if get('entity:Calendar','watered_growth','condition') is not True:raise ValidationError('WATERING_PRECONDITION')
        if rule_id=='growth_timing':
            if any(x['id']==e and x['type']=='Seed' for x in body['entities']):e=get(e,'grows_into','entity')
            seasons=get(e,'season','season');seasons=[seasons] if isinstance(seasons,str) else seasons
            if params['season'] not in seasons:return {'status':'UNSUPPORTED_CONDITIONS','reason':'season'}
            day=integer(params['day'],'day',1);last=get('entity:Calendar','season_days','days');duration=get(e,'growth_days','growth_nights')
            if day>last:raise ValidationError('DATE_OUT_OF_RANGE')
            out={'first_harvest_day':day+duration,'within_season':day+duration<=last,'effective_growth_nights':duration,'season':params['season']}
            steps=[f'{day} + {duration} = {day+duration}; last season day {last}']
        else:
            durations=get(e,'stage_durations','growth_nights');stage=integer(params['stage'],'stage',1);interval=stage_remaining(durations,stage)
            if params.get('elapsed_in_stage') is not None:
                elapsed=integer(params['elapsed_in_stage'],'elapsed_in_stage')
                if stage>len(durations) or elapsed>=durations[stage-1]:raise ValidationError('STAGE_ELAPSED_CONFLICT')
                exact=sum(durations[stage-1:])-elapsed;interval=[exact,exact]
            out={'remaining_growth_nights':interval,'stage':stage};steps=['Only confirmed effective growth nights narrow the interval.']
    elif rule_id=='processing_value':
        p=params['product_id'];formula=get(p,'value_formula','g');machine=get(p,'equipment','entity')
        get(e,'category','category');base=get(e,'sell_normal','g');raw=get(e,'sell_'+params['quality'],'g')
        out=process_value(base,raw,formula['multiplier'],formula['offset'],params['quantity']);out['equipment']=machine;out['schedule_supported']=False
        steps=[f"{base} × {formula['multiplier']} + {formula['offset']} = {out['unit_value_g']} g per processed item"]
    elif rule_id=='crafting_gap':
        out=crafting(get(e,'materials','items'),params['quantity'],params['inventory'],get(e,'farming_level','level'),params['user_level'])
        steps=['required quantity × target count − observed inventory, floored at zero']
    elif rule_id=='bundle_reserve':
        req=get(e,'requirements','requirements');choose=get(e,'choose_k','requirements')
        if not isinstance(params['completed'],list):return {'status':'INVALID_INPUT','field':'completed','expected':'array of completed item names; [] means none'}
        # Identity case normalization uses only requirements present in this bundle.
        def name_key(value):return value.replace('_',' ').casefold()
        names_by_case={name_key(r['item']):r['item'] for r in req}
        completed={names_by_case.get(name_key(x),x) for x in params['completed']}
        inventory={};original=params['inventory']
        for name,stock in original.items():
            normalized=names_by_case.get(name_key(name),name)
            if normalized in inventory:raise ValidationError('DUPLICATE_INVENTORY_IDENTITY')
            if not isinstance(stock,dict) or set(stock)-set(QUALITY):raise ValidationError('INVENTORY_QUALITY_SCHEMA')
            inventory[normalized]={q:integer(n,'inventory_quantity') for q,n in stock.items()}
        names={r['item'] for r in req}
        if not completed<=names:raise ValidationError('UNKNOWN_COMPLETED_REQUIREMENT')
        needed=max(0,choose-len(completed));eligible=[]
        for row in req:
            if row['item'] in completed:continue
            stock=inventory.get(row['item'],{});minq=QUALITY[row['quality']]
            available=sum(integer(stock.get(q,0),q) for q in QUALITY if QUALITY[q]>=minq)
            if available>=row['quantity']:eligible.append(row)
        options=[]
        for choice in combinations(eligible,needed):
            reserve={};remaining={k:dict(v) for k,v in inventory.items()}
            for row in choice:
                rest=row['quantity'];alloc={}
                for q in QUALITY:
                    if QUALITY[q]<QUALITY[row['quality']]:continue
                    n=min(rest,remaining[row['item']].get(q,0));alloc[q]=n;remaining[row['item']][q]=remaining[row['item']].get(q,0)-n;rest-=n
                reserve[row['item']]=alloc
            options.append({'reserved':reserve,'remaining':remaining})
        out={'choose_remaining':needed,'options':options,'inventory_observed_unchanged':True,'normalized_inventory':inventory,'status':'FEASIBLE' if options else 'INSUFFICIENT_INVENTORY'}
        steps=['Choose required remaining options; allocate each inventory item once in each independent plan copy.']
    used={f['id']:f for f in used};rels={r['id']:r for r in relations}
    trace={'run_id':ident('calculation',body['bundle_id'],rule_id,params),'status':'OK' if formal else 'CANDIDATE_RESULT_NOT_RELEASED',
        'rule_id':rule_id,'rule_version':RULES[rule_id]['rule_version'],'rule_fingerprint':rule_fingerprint(rule_id),'bundle_id':body['bundle_id'],'snapshot_id':body['snapshot_id'],
        'task_id':body['task_id'],'task_revision':body['task_revision'],'user_inputs':params,'evidence_inputs':list(used.values()),
        'outputs':out,'intermediate_steps':steps,'used_fact_ids':list(used),'used_relation_ids':list(rels),
        'used_evidence_ids':sorted({x for r in list(used.values())+list(rels.values()) for x in r['evidence_ids']}),
        'limitations':['Candidate rule and knowledge require human audit before formal use.'] if not formal else []}
    return trace
