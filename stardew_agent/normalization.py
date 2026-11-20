"""Explicit, traceable candidate migration. Never mutate a source snapshot."""
from __future__ import annotations
import copy
from .core import digest, ident, ValidationError, validate_graph

GROUPS = ('entities','facts','relations','evidence','assets','occurrences','regions','observations','alignments')
CANONICAL_TYPES = {'Crop','CropStage','Season','Category','Seed','Item','Equipment','EquipmentType',
                   'Product','Recipe','Rule','RuleSubject','Entity','NPC','Location','Shop','Bundle','Quest'}
FACT_PREDICATES = {'growth_days','season','category','sell_normal','sell_silver','sell_gold','sell_iridium',
    'stage_durations','duration','grows_into','regrowth','base_yield','season_days','watered_growth','materials',
    'farming_level','processing_minutes','value_formula','equipment','machine_day','choose_k','quality_bundle','requirements'}
RELATION_PREDICATES = {'GROWS_IN_SEASON','INSTANCE_OF','HAS_STAGE','NEXT_STAGE','GROWS_INTO','USES_EQUIPMENT',
    'PRODUCES','CONSUMES','PRODUCED_BY','CAN_PROCESS','BUNDLE_REQUIREMENT'}
DEFAULT_POLICY = {'version':'conservative-case/v1','type_map':{t.lower():t for t in CANONICAL_TYPES},
                  'predicate_map':{},'entity_map':{}}


def _replace(value, mapping, key=None):
    # IDs may occur inside conditions/material dictionaries. Source quotations,
    # locators and visible descriptions remain verbatim evidence.
    if key in {'quote','near_text','visible_description','reason_summary','name','aliases','legacy_ids','migration'}:
        return value
    if isinstance(value, str):return mapping.get(value,value)
    if isinstance(value, list):return [_replace(v,mapping,key) for v in value]
    if isinstance(value, dict):return {mapping.get(k,k):_replace(v,mapping,k) for k,v in value.items()}
    return value


def normalize_graph(domain, policy=None):
    """Return graph/migration/issues; entity_map is an explicit old-ID -> existing-ID map.

    Predicate maps may be shared (`predicate_map`) or scoped using `fact_predicate_map`
    and `relation_predicate_map`. No fuzzy matching, singularization or inferred merge.
    Unknown vocabulary remains an unapproved candidate and is reported.
    """
    policy=copy.deepcopy(DEFAULT_POLICY if policy is None else policy)
    graph=copy.deepcopy(domain);changes=[];issues=[];mapping={}
    entities={r['id']:r for r in graph.get('entities',[])}
    requested=policy.get('entity_map',{})
    for old in requested:
        current=old;seen=set()
        while current in requested and requested[current]!=current:
            if current in seen:raise ValidationError('MIGRATION_ENTITY_CYCLE')
            seen.add(current);current=requested[current]
        if current not in entities:raise ValidationError('MIGRATION_UNKNOWN_TARGET:'+current)
        if old not in entities:
            if old in entities[current].get('legacy_ids',[]):continue
            raise ValidationError('MIGRATION_UNKNOWN_ENTITY:'+old)
        if current!=old:mapping[old]=current
    # Put target records first so the explicit canonical target controls naming/type.
    order=sorted(graph.get('entities',[]),key=lambda r:r['id'] in mapping)
    for row in order:
        old_type=row['type'];row['type']=policy.get('type_map',{}).get(old_type,old_type)
        if old_type!=row['type']:changes.append({'kind':'type','id':row['id'],'from':old_type,'to':row['type']})
        if row['type'] not in CANONICAL_TYPES:issues.append({'code':'UNKNOWN_ENTITY_TYPE','id':row['id'],'value':row['type']})
    graph['entities']=order
    canonical_types={row['id']:row['type'] for row in order}
    for row in graph['entities']:
        if row['id'] in mapping:row['type']=canonical_types[mapping[row['id']]]
    graph={k:([_replace(r,mapping) for r in v] if k in GROUPS else v) for k,v in graph.items()}
    # Unit=entity is an identity reference, not arbitrary prose. Resolve only an
    # exact, unique known ID/name/alias; ambiguity remains visible for review.
    entity_names={}
    for row in graph['entities']:
        for name in [row['id'],row['id'].removeprefix('entity:'),row['name'],*row.get('aliases',[])]:entity_names.setdefault(name,set()).add(row['id'])
    for group in ('facts','relations'):
        specific='fact_predicate_map' if group=='facts' else 'relation_predicate_map'
        vocabulary=FACT_PREDICATES if group=='facts' else RELATION_PREDICATES
        for row in graph.get(group,[]):
            old_id=row['id'];old_pred=row['predicate']
            row.update(_replace(row,mapping))
            if group=='facts' and row.get('unit')=='entity' and isinstance(row.get('value'),str):
                matches=entity_names.get(row['value'],set())
                if len(matches)==1:row['value']=next(iter(matches))
                else:issues.append({'code':'AMBIGUOUS_ENTITY_VALUE' if matches else 'UNKNOWN_ENTITY_VALUE','id':old_id,'value':row['value']})
            row['predicate']=policy.get(specific,{}).get(old_pred,policy.get('predicate_map',{}).get(old_pred,old_pred))
            if row['predicate'] not in vocabulary:issues.append({'code':'UNKNOWN_PREDICATE','id':old_id,'group':group,'value':row['predicate']})
            original=next(r for r in domain[group] if r['id']==old_id)
            fields=('subject','predicate','value','unit','conditions') if group=='facts' else ('subject','predicate','object','conditions')
            if any(row.get(k)!=original.get(k) for k in fields):
                new_id=ident('fact' if group=='facts' else 'relation',*(row[k] for k in fields))
                row['id']=new_id;mapping[old_id]=new_id
                changes.append({'kind':group,'id':old_id,'to':new_id,'fields':[k for k in fields if row.get(k)!=original.get(k)]})
    # All dependency references follow re-keyed facts/relations before alignment IDs.
    graph={k:([_replace(r,mapping) for r in v] if k in GROUPS else v) for k,v in graph.items()}
    if changes:
        for group in ('facts','relations','alignments'):
            for row in graph.get(group,[]):
                if row.get('review_status')!='conflicted':row['review_status']='candidate'
                row['answer_allowed']=False;row.pop('approval',None)
    originals={r['id']:r for r in domain.get('alignments',[])}
    for row in graph.get('alignments',[]):
        original=originals[row['id']]
        if row.get('method')=='stage_sequence_illustration/v1':
            relation_row=next((r for r in graph.get('relations',[]) if r['id']==row['target_id']),None)
            support=[]
            if relation_row:
                for endpoint in (relation_row['subject'],relation_row['object']):
                    candidates=[a for a in graph['alignments'] if a.get('target_kind')=='state' and a.get('target_id')==endpoint
                                and a.get('occurrence_id') in row.get('support_occurrence_ids',[]) and a.get('status')=='matched']
                    if candidates:support.append(candidates[0]['id'])
            row['support_relation_ids']=[row['target_id']]
            row['support_alignment_ids']=support
            if len(support)!=2:
                row['derivation_inputs_incomplete']=True
                issues.append({'code':'ILLUSTRATION_DEPENDENCIES_INCOMPLETE','id':row['id']})
        if 'confirmation_level' not in row:
            method=row.get('method','')
            row['confirmation_level']=('structural_illustration' if method=='stage_sequence_illustration/v1' else
                'legacy_model_candidate' if 'mllm_alignment' in method else 'structural_candidate')
            changes.append({'kind':'confirmation_level','id':row['id'],'to':row['confirmation_level']})
        if row!=original:
            old_id=row['id'];new_id=ident('alignment',old_id,'explicit-migration',digest({k:v for k,v in row.items() if k!='id'}))
            row['id']=new_id;mapping[old_id]=new_id;changes.append({'kind':'alignments','id':old_id,'to':new_id})
    graph={k:([_replace(r,mapping) for r in v] if k in GROUPS else v) for k,v in graph.items()}
    for group in ('entities','facts','relations','alignments'):
        for row in graph.get(group,[]):
            prior=[old for old,new in mapping.items() if new==row['id']]
            if prior:row['legacy_ids']=sorted(set(row.get('legacy_ids',[])+prior))
            if prior or any(c.get('id')==row['id'] for c in changes):
                row.update(review_status='candidate',answer_allowed=False)
                row.pop('approval',None)
            if group in ('facts','relations','alignments'):row['dependency_contract']='v1'
    # Explicitly merged names become aliases, including the original canonical name.
    for old,new in mapping.items():
        if old in entities:
            target=next(r for r in graph['entities'] if r['id']==new)
            target['aliases']=sorted(set(target.get('aliases',[])+entities[old].get('aliases',[])+[entities[old]['name']]))
            changes.append({'kind':'entity_id','id':old,'to':new})
    from .construction import merge_graphs
    merged=merge_graphs([graph]);validate_graph(merged)
    return {'graph':merged,'migration':{'schema':'graph-migration/v1','policy':policy,'policy_hash':digest(policy),
            'input_hash':digest(domain),'output_hash':digest(merged),'id_map':mapping,'changes':changes},'issues':issues}
