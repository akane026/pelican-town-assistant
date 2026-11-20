"""Capability descriptors and dependencies, independent of example questions."""
from .core import ValidationError,DATA,ROOT,read,write,digest,file_hash,now

RULES={
 'sale_value':{'description':'已知物品、数量、品质和职业，计算直接销售价值','inputs':['entity_id','quantity','quality','profession']},
 'growth_timing':{'description':'根据季节、日期、浇水条件计算首次成熟日，不做产量优化','inputs':['entity_id','day','season','watered','acceleration']},
 'processing_value':{'description':'比较已有原料直接卖与指定加工产物的最终价值，不保证加工完成日期','inputs':['entity_id','product_id','quantity','quality','profession']},
 'crafting_gap':{'description':'设备制作材料缺口及解锁条件','inputs':['entity_id','quantity','inventory','user_level']},
 'bundle_reserve':{'description':'按已覆盖收集包的要求、品质和完成状态，在计划副本预留库存，支持n选k','inputs':['entity_id','inventory','completed']},
 'stage_remaining':{'description':'已确认作物生长阶段的剩余夜晚区间，可用阶段内已过天数收紧','inputs':['entity_id','stage','watered','acceleration']}}
for key,r in RULES.items():r.update(rule_id=key,rule_version='1',implementation_version='v3.1',audit_status='assistant_tested_human_pending',globally_optimal=False)
PARAM_SCHEMA={'type':'object','properties':{
 'entity_id':{'type':'string'},'product_id':{'type':'string'},'quantity':{'type':'integer','minimum':0},
 'quality':{'type':'string','enum':['normal','silver','gold','iridium']},'profession':{'type':'string'},
 'day':{'type':'integer','minimum':1},'season':{'type':'string','enum':['Spring','Summer','Fall','Winter']},
 'watered':{'type':'boolean'},'acceleration':{'type':'string'},'inventory':{'type':'object','description':'Canonical English item names mapped to quality counts, e.g. {"Parsnip":{"normal":10}}'},
 'completed':{'type':'array','items':{'type':'string'},'description':'Names of already completed requirements; [] if none. Never a boolean.'},
 'user_level':{'type':'integer','minimum':0},'stage':{'type':'integer','minimum':1},'elapsed_in_stage':{'type':'integer','minimum':0},'plan_option':{'type':'integer','minimum':0}},'additionalProperties':False}
for key,r in RULES.items():r['parameter_schema']={'type':'object','properties':{k:PARAM_SCHEMA['properties'][k] for k in r['inputs']},'required':r['inputs']}

_IMPLEMENTATION_PATHS=['stardew_agent/calculations.py','stardew_agent/rules.py','verification/calculators.py']
_LOADED_IMPLEMENTATIONS={path:file_hash(ROOT/path) for path in _IMPLEMENTATION_PATHS}

def rule_fingerprint(rule_id):
    if rule_id not in RULES:raise ValidationError('UNKNOWN_RULE')
    if any(file_hash(ROOT/path)!=sha for path,sha in _LOADED_IMPLEMENTATIONS.items()):
        raise ValidationError('RULE_IMPLEMENTATION_CHANGED_RESTART_REQUIRED')
    return digest([RULES[rule_id],_LOADED_IMPLEMENTATIONS])

def rule_audit(rule_id):
    p=DATA/'reviews/rules.json';rows=read(p) if p.exists() else {}
    row=rows.get(rule_id,{})
    if row.get('fingerprint')==rule_fingerprint(rule_id) and row.get('actor')=='local_user' and row.get('action')=='approve' and row.get('reason'):
        return {'status':'approved_human',**row}
    return {'status':'assistant_tested_human_pending'}

def record_rule_review(rule_id,action,reason):
    if action not in ('approve','reject') or not str(reason).strip():raise ValidationError('RULE_REVIEW_REASON_REQUIRED')
    fingerprint=rule_fingerprint(rule_id);p=DATA/'reviews/rules.json';rows=read(p) if p.exists() else {}
    rows[rule_id]={'fingerprint':fingerprint,'actor':'local_user','action':action,'reason':reason,'at':now()};write(p,rows);return rows[rule_id]

def referenced_entity(value,body):
    """Resolve legacy entity-valued fields using only bundled identities."""
    candidates=[e['id'] for e in (body or {}).get('entities',[]) if value==e['id'] or value==e.get('name') or str(value).replace(' ','_')==e['id'].removeprefix('entity:')]
    if len(set(candidates))==1:return candidates[0]
    # Legacy unit='entity' stored the canonical Wiki title without the namespace.
    # Constructing its identifier does not assert it exists; the subsequent
    # directed-edge dependency must still be retrieved and validated.
    if not candidates and isinstance(value,str) and not value.startswith('entity:'):return 'entity:'+value.replace(' ','_')
    return value

def dependencies(rule_id,params,body=None):
    if rule_id not in RULES:raise ValidationError('UNKNOWN_RULE')
    missing_inputs=[k for k in RULES[rule_id]['inputs'] if params.get(k) is None]
    entity=params.get('entity_id');sels=[]
    def f(s,p,u):sels.append({'kind':'fact','subject':s,'predicate':p,'unit':u,'__context':params})
    def r(s,p,o=None):
        sel={'kind':'relation','subject':s,'predicate':p,'__context':params}
        if o:sel['object']=o
        sels.append(sel)
    if not entity:return {'selectors':[],'missing_inputs':missing_inputs}
    if rule_id=='sale_value':f(entity,'sell_'+str(params.get('quality','normal')),'g')
    elif rule_id=='growth_timing':
        # Whether input is a seed is supplied by actual bundle entity type, not name spelling.
        types={e['id']:e['type'] for e in (body or {}).get('entities',[])}
        if types.get(entity)=='Seed':
            f(entity,'grows_into','entity')
            targets=[x['value'] for x in (body or {}).get('facts',[]) if x['subject']==entity and x['predicate']=='grows_into']
            if not targets:return {'selectors':sels,'missing_inputs':missing_inputs,'dependency_discovery_incomplete':True}
            target=referenced_entity(targets[0],body);r(entity,'GROWS_INTO',target)
            entity=target
        f(entity,'growth_days','growth_nights');f(entity,'season','season');f('entity:Calendar','season_days','days');f('entity:Calendar','watered_growth','condition')
    elif rule_id=='processing_value':
        p=params.get('product_id')
        f(entity,'sell_normal','g');f(entity,'sell_'+str(params.get('quality','normal')),'g');f(entity,'category','category')
        if p:
            f(p,'value_formula','g');f(p,'equipment','entity');r(entity,'CAN_PROCESS',p)
            machines=[x['value'] for x in (body or {}).get('facts',[]) if x['subject']==p and x['predicate']=='equipment']
            if not machines:return {'selectors':sels,'missing_inputs':missing_inputs,'dependency_discovery_incomplete':True}
            r(p,'PRODUCED_BY',referenced_entity(machines[0],body))
    elif rule_id=='crafting_gap':f(entity,'materials','items');f(entity,'farming_level','level')
    elif rule_id=='bundle_reserve':f(entity,'requirements','requirements');f(entity,'choose_k','requirements')
    elif rule_id=='stage_remaining':f(entity,'stage_durations','growth_nights');f('entity:Calendar','watered_growth','condition');r(entity,'HAS_STAGE')
    return {'selectors':sels,'missing_inputs':missing_inputs}

def matches_selector(row,selector):
    """Match a dependency's identity AND its applicable evidence conditions.

    Provenance and structural annotations are not user preconditions. Unknown
    semantic conditions are deliberately not treated as universally true.
    """
    if not all(row.get(k)==v for k,v in selector.items() if k not in ('kind','__context')):return False
    if '__context' not in selector:return True
    conditions=row.get('conditions') or {}
    if not isinstance(conditions,dict):return False
    metadata={'game_version','knowledge_scope','derivation','ordinal','rule_version','sequence_basis'}
    context=dict(selector['__context'])
    # Processing deliberately requests the normal base price even when the
    # input is gold quality; the requested predicate identifies that operand.
    if str(selector.get('predicate','')).startswith('sell_'):
        context['quality']=selector['predicate'][5:]
    if selector.get('predicate')=='HAS_STAGE' and context.get('stage') is not None:
        if conditions.get('ordinal')!=context['stage']:return False
    for key,value in conditions.items():
        if key in metadata:
            if key=='game_version' and context.get(key) is not None and context[key]!=value:return False
            continue
        if key not in context or context[key]!=value:return False
    return True

def missing_dependencies(body,selectors):
    missing=[]
    for sel in selectors:
        group=body['facts'] if sel['kind']=='fact' else body['relations']
        if not any(matches_selector(row,sel) for row in group):missing.append(sel)
    return missing
