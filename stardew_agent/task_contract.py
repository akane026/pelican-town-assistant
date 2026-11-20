"""User-anchored runtime goals and server-derived coverage, never an evaluation key.

The model may propose a decomposition. It cannot certify that the decomposition
is semantically exhaustive or mark a goal complete. Independent evaluation must
provide its own expected goals, outside this runtime contract.
"""
from __future__ import annotations
from .core import ValidationError, canonical, digest

GOAL_KINDS={'knowledge','explanation','calculation','comparison','identification','visual_candidates'}
GOAL_FIELDS={'id','kind','user_quote','source_turn_id','entity_id','params','rule_ids','product_ids','predicates','region_id','inventory_scope'}

def normalize_goals(spec, task):
    if not isinstance(spec,dict) or set(spec)-{'goals'}:raise ValidationError('INVALID_GOAL_SPEC')
    goals=spec.get('goals')
    if not isinstance(goals,list) or not 1<=len(goals)<=16:raise ValidationError('GOALS_REQUIRED_OR_BUDGET_EXCEEDED')
    turns={t['turn_id']:t['text'] for t in task.get('user_turns',[])}
    normalized=[];seen=set()
    for raw in goals:
        if not isinstance(raw,dict) or set(raw)-GOAL_FIELDS:raise ValidationError('INVALID_GOAL_FIELDS')
        g=dict(raw);gid=g.get('id');kind=g.get('kind');quote=g.get('user_quote')
        if not isinstance(gid,str) or not gid or len(gid)>80 or gid in seen:raise ValidationError('INVALID_GOAL_ID')
        if kind not in GOAL_KINDS:raise ValidationError('INVALID_GOAL_KIND')
        turn=g.get('source_turn_id') or task.get('current_turn_id')
        from .state import valid_source_excerpt
        if not isinstance(quote,str) or not quote.strip() or not valid_source_excerpt(quote,turns.get(turn,'')):raise ValidationError('GOAL_QUOTE_NOT_IN_USER_TURN')
        if not isinstance(g.get('params',{}),dict):raise ValidationError('INVALID_GOAL_PARAMS')
        for field in ('rule_ids','product_ids','predicates'):
            if not isinstance(g.get(field,[]),list) or any(not isinstance(x,str) for x in g.get(field,[])):raise ValidationError('INVALID_GOAL_CONSTRAINTS')
            g[field]=list(dict.fromkeys(g.get(field,[])))
        if kind in ('calculation','comparison') and not g['rule_ids']:raise ValidationError('GOAL_RULE_REQUIRED')
        if kind=='comparison' and len(g['product_ids'])<2 and len(g['rule_ids'])<2:raise ValidationError('COMPARISON_ALTERNATIVES_REQUIRED')
        if g.get('inventory_scope','observed') not in ('observed','remaining'):raise ValidationError('INVALID_INVENTORY_SCOPE')
        g.update(source_turn_id=turn,params=g.get('params',{}),inventory_scope=g.get('inventory_scope','observed'))
        normalized.append(g);seen.add(gid)
    return {'goals':normalized,'task_revision':task['revision'],'turn_id':task.get('current_turn_id'),
            'request_text':turns.get(task.get('current_turn_id'),''),'origin':'model_proposed_user_anchored',
            'independently_verified':False,'semantic_exhaustiveness_verified':False,
            'contract_id':'contract:'+digest([task['task_id'],task.get('current_turn_id'),normalized])[:24]}

def matching_goals(task,rule_id,params,goal_id=None):
    goals=task.get('goal_spec',{}).get('goals',[])
    if goal_id is not None and not any(g['id']==goal_id for g in goals):raise ValidationError('UNKNOWN_GOAL_ID')
    matches=[]
    for g in goals:
        if goal_id is not None and g['id']!=goal_id:continue
        if g['kind'] not in ('calculation','comparison') or rule_id not in g['rule_ids']:continue
        if g.get('entity_id') and params.get('entity_id')!=g['entity_id']:continue
        if g.get('product_ids') and 'product_id' in params and params['product_id'] not in g['product_ids']:continue
        if any(params.get(k)!=v for k,v in g.get('params',{}).items()):continue
        matches.append(g)
    return matches

def parameter_binding(task,rule_id,params,required,*,goal_id=None,identity_aliases=None,alias_catalog_sha256=None,evidence_body=None,product_identity_ids=None):
    """Compare execution operands with recorded inputs; no inferred game values.

    Entity/product IDs may be proposed by the goal resolver. User-dependent
    operands require state provenance. A model-extracted quote remains labeled
    as extraction, not human confirmation.
    """
    goals=matching_goals(task,rule_id,params,goal_id)
    if not goals:return {'status':'GOAL_PARAMETER_MISMATCH','reason':'Register a user-anchored goal matching this rule, entity and parameter set.'}
    inputs=task.get('inputs',{});sources=task.get('input_sources',{})
    scoped=inputs.get('entity_inputs',{}).get(params.get('entity_id'),{})
    item=params.get('entity_id','').split(':',1)[-1]
    inventory_row=next((v for k,v in inputs.get('inventory',{}).items() if k.casefold()==item.casefold()),{})
    confirmation_origin=sources.get('confirmed_entities',{})
    human=confirmation_origin.get('human_confirmation') is True and confirmation_origin.get('source') in ('user_ui','user_confirmation')
    region_ids={r['region_id'] for r in task.get('selected_regions',[]) if isinstance(r,dict) and isinstance(r.get('region_id'),str)}
    confirmed_map={rid:row for rid,row in inputs.get('confirmed_entities',{}).items() if human and rid in region_ids and isinstance(row,dict)}
    confirmed=[x for x in confirmed_map.values() if x.get('entity_id')==params.get('entity_id')]
    bindings={};missing=[];conflicts=[]
    target=params.get('entity_id')
    scoped_identity=target in inputs.get('entity_inputs',{}) or bool(inventory_row) or bool(confirmed)
    identity_conflicts=[]
    for g in goals:
        region=confirmed_map.get(g.get('region_id'),{})
        if region and region.get('entity_id')!=target:identity_conflicts.append({'field':'entity_id','recorded':region.get('entity_id'),'requested':target,'region_id':g['region_id']})
    # A global identity applies unless another explicit scoped input establishes
    # this target. Merely listing a second model-proposed goal is not evidence.
    if inputs.get('entity_id') and inputs['entity_id']!=target and not scoped_identity:
        identity_conflicts.append({'field':'entity_id','recorded':inputs['entity_id'],'requested':target})
    if not inputs.get('entity_id') and confirmed_map and not scoped_identity:
        identity_conflicts.append({'field':'entity_id','recorded':sorted({r.get('entity_id') for r in confirmed_map.values() if isinstance(r,dict) and r.get('entity_id')}),'requested':target})
    from .retrieval import unique_identity_mention
    turns={r['turn_id']:r['text'] for r in task.get('user_turns',[])}
    def anchored_identity(eid,g):
        full=turns.get(g.get('source_turn_id'),'')
        return bool(g.get('user_quote') and g['user_quote'] in full and unique_identity_mention(eid,full,identity_aliases or {}))
    if inputs.get('product_id') and params.get('product_id') and inputs['product_id']!=params['product_id']:
        # Multiple products are deliberate comparison alternatives, not an
        # overwrite of a single confirmed product identity.
        if not any(g['kind']=='comparison' and params['product_id'] in g['product_ids'] and anchored_identity(params['product_id'],g) for g in goals):identity_conflicts.append({'field':'product_id','recorded':inputs['product_id'],'requested':params['product_id']})
    if identity_conflicts:return {'status':'INPUT_CONFLICT','conflicts':identity_conflicts,'reason':'Resolved identity conflicts with recorded/confirmed user identity.'}
    if confirmed:
        from .state import registered_regions
        try:valid_regions=registered_regions(task)
        except (ValueError,KeyError,TypeError,OSError):valid_regions={}
        confirmed=[r for rid,r in confirmed_map.items() if rid in valid_regions and r.get('entity_id')==target]
    for g in goals:
        if g.get('region_id') and not any(confirmed_map.get(g['region_id'])==r for r in confirmed):
            return {'status':'NEEDS_CONFIRMATION','missing_inputs':['confirmed_entities'],'reason':'An image candidate cannot authorize calculation; confirm this registered region in the workbench.'}
    for key in set(required)|({'elapsed_in_stage'} if 'elapsed_in_stage' in params else set()):
        if key not in params:continue # calculator reports the missing operand
        if key in ('entity_id','product_id'):
            if inputs.get(key)==params[key] and sources.get(key):bindings[key]=sources[key]
            elif key=='entity_id' and confirmed:bindings[key]={'source':'user_confirmation','entity_id':target}
            elif key=='entity_id' and target in inputs.get('entity_inputs',{}) and sources.get('entity_inputs'):bindings[key]=sources['entity_inputs']
            elif key=='entity_id' and inventory_row and sources.get('inventory'):bindings[key]=sources['inventory']
            else:
                anchors=[g for g in goals if anchored_identity(params[key],g)]
                if anchors:bindings[key]={'source':'user_text_identity_match','goal_ids':[g['id'] for g in anchors],
                    'evidence_quotes':[g['user_quote'] for g in anchors],'alias_catalog_sha256':alias_catalog_sha256,'human_confirmation':False}
                elif key=='product_id' and rule_id=='processing_value' and evidence_body:
                    from .rules import matches_selector
                    selector={'kind':'relation','subject':target,'predicate':'CAN_PROCESS','object':params[key],'__context':params}
                    valid_body=all(evidence_body.get(k)==task.get(tk) for k,tk in (('task_id','task_id'),('task_revision','revision'),('snapshot_id','snapshot_id')))
                    relations=[r for r in evidence_body.get('relations',[]) if valid_body and matches_selector(r,selector)]
                    # An explicit product selection bounds the alternatives;
                    # graph reachability cannot silently replace that choice.
                    # Explicit user selections are lexical constraints from the
                    # complete identity catalog, not limited by the retrieved
                    # slice. A partial Wine-only bundle must not erase a named
                    # Jelly constraint. This catalog only restricts selection;
                    # it supplies no relation, value, or calculation evidence.
                    catalog_products=set(product_identity_ids) if product_identity_ids is not None else set(identity_aliases or {})-{target}
                    named={p for p in catalog_products if any(anchored_identity(p,g) for g in goals)}
                    if relations and (not named or params[key] in named) and (not inputs.get('product_id') or inputs['product_id']==params[key]):
                        bindings[key]={'source':'explicit_bundle_processing_relation','bundle_id':evidence_body.get('bundle_id'),
                            'relation_ids':[r['id'] for r in relations],'evidence_ids':sorted({e for r in relations for e in r.get('evidence_ids',[])}),
                            'task_revision':task['revision'],'snapshot_id':task['snapshot_id'],'human_confirmation':False}
                    else:missing.append(key)
                else:missing.append(key)
            continue
        if key=='quantity' and any(g['inventory_scope']=='remaining' for g in goals):
            bindings[key]={'source':'reservation_remaining','pending_plan_check':True};continue
        if key in scoped:
            expected=scoped[key];origin=sources.get('entity_inputs')
        elif key in inputs:
            expected=inputs[key];origin=sources.get(key)
        elif key=='quality' and params[key] in inventory_row:
            expected=params[key];origin=sources.get('inventory')
        elif key=='quantity' and params.get('quality') in inventory_row:
            expected=inventory_row[params['quality']];origin=sources.get('inventory')
        else:
            rows=[r for r in confirmed if key in r]
            if len(rows)==1:expected=rows[0][key];origin={'source':'user_confirmation','region_entity':params.get('entity_id')}
            else:missing.append(key);continue
        if not origin:missing.append(key)
        elif expected!=params[key]:conflicts.append({'field':key,'recorded':expected,'requested':params[key]})
        else:bindings[key]=origin
    if conflicts:return {'status':'INPUT_CONFLICT','conflicts':conflicts,'reason':'Tool operands differ from recorded user inputs.'}
    if missing:return {'status':'NEEDS_INPUT','missing_inputs':sorted(missing),'reason':'Record user-supplied operands and their source before execution.'}
    return {'status':'BOUND','goal_ids':[g['id'] for g in goals],'parameter_sources':bindings}

def bind_plan(task,rule_id,params,goals,requested_plan_id=None):
    if rule_id not in ('sale_value','processing_value'):return None
    plan=task.get('inventory_plan_copy',{})
    remaining=any(g.get('inventory_scope')=='remaining' for g in goals)
    if not remaining and not requested_plan_id:return None
    if not plan or not plan.get('plan_id'):return {'status':'MISSING_INVENTORY_PLAN'}
    if requested_plan_id!=plan['plan_id']:return {'status':'INVENTORY_PLAN_ID_MISMATCH','expected_plan_id':plan['plan_id']}
    if plan.get('task_revision')!=task['revision'] or plan.get('snapshot_id')!=task['snapshot_id']:return {'status':'STALE_INVENTORY_PLAN'}
    if plan.get('status')=='INSUFFICIENT_INVENTORY' or not plan.get('options'):return {'status':'INVENTORY_PLAN_INFEASIBLE'}
    options=plan['options'];selection=params.get('plan_option')
    if selection is None and len(options)>1:return {'status':'NEEDS_INPUT','missing_inputs':['plan_option']}
    selection=0 if selection is None else selection
    if type(selection)!=int or not 0<=selection<len(options):return {'status':'INVALID_PLAN_OPTION'}
    if len(options)>1 and task.get('inputs',{}).get('plan_option')!=selection:return {'status':'NEEDS_INPUT','missing_inputs':['plan_option'],'reason':'Reservation alternatives require an explicit recorded selection.'}
    item=params.get('entity_id','').split(':',1)[-1]
    stock=next((v for k,v in options[selection]['remaining'].items() if k.casefold()==item.casefold()),None)
    if stock is None:return {'status':'INVENTORY_ITEM_NOT_IN_PLAN','entity_id':params.get('entity_id')}
    available=stock.get(params.get('quality'),0);quantity=params.get('quantity')
    if type(quantity)!=int or quantity<0 or quantity>available or (remaining and quantity!=available):
        return {'status':'INVENTORY_PLAN_CONFLICT','available':available,'requested':quantity}
    return {'status':'BOUND','plan_id':plan['plan_id'],'reservation_run_id':plan['reservation_run_id'],
            'plan_option':selection,'task_revision':task['revision'],'snapshot_id':task['snapshot_id'],
            'inventory_scope':'remaining','available':available}

def goal_evidence_matches(goal,refs,evidence):
    rows=[evidence[r] for r in refs if r in evidence]
    if not rows:return False
    entity=goal.get('entity_id')
    if entity:
        rows=[r for r in rows if entity in (r.get('subject'),r.get('object'),r.get('entity_id')) or entity in r.get('entity_ids',[])]
        if not rows:return False
    return set(goal.get('predicates',[]))<={r.get('predicate') for r in rows}

def current_visual_receipts(task,receipts):
    from .state import registered_regions
    try:regions=registered_regions(task)
    except (ValueError,KeyError,TypeError,OSError):return {}
    return {rid:r for rid,r in receipts.items() if r.get('receipt_id')==rid and rid in task.get('visual_results',[])
        and r.get('task_id')==task['task_id'] and r.get('task_revision')==task['revision'] and r.get('snapshot_id')==task['snapshot_id']
        and r.get('region_id') in regions and r.get('query_sha256')==regions[r['region_id']]['sha256']
        and r.get('automatic_identity_confirmation') is False}

def coverage(task,calculations,evidence,checked_sections=(),*,fingerprints=None,visual_receipts=None):
    """Coverage of registered goals only, independent of the model's final status."""
    spec=task.get('goal_spec',{});goals=spec.get('goals',[])
    current=[]
    for c in calculations.values():
        if c.get('task_revision')!=task['revision'] or c.get('snapshot_id')!=task['snapshot_id']:continue
        if c.get('run_id') not in task.get('results',[]):continue
        if task['execution_mode']=='released' and c.get('status')!='OK':continue
        if fingerprints is not None and c.get('rule_fingerprint')!=fingerprints.get(c.get('rule_id')):continue
        current.append(c)
    statuses=[]
    for g in goals:
        refs=[];reason='No current supported result for this goal.'
        if g['kind'] in ('knowledge','explanation'):
            for section in checked_sections:
                if section.get('goal_id')==g['id'] and goal_evidence_matches(g,section.get('evidence_refs',[]),evidence):refs+=section['evidence_refs']
        elif g['kind']=='visual_candidates':
            refs=[rid for rid,r in current_visual_receipts(task,visual_receipts or {}).items() if r['region_id']==g.get('region_id')]
            reason='No current registered-region candidate receipt; a candidate list never confirms identity.'
        elif g['kind']=='identification':
            confirmed=task.get('inputs',{}).get('confirmed_entities',{})
            row=confirmed.get(g.get('region_id'),{})
            region_ids={r['region_id'] for r in task.get('selected_regions',[]) if isinstance(r,dict) and isinstance(r.get('region_id'),str)}
            origin=task.get('input_sources',{}).get('confirmed_entities',{})
            human=origin.get('human_confirmation') is True and origin.get('source') in ('user_ui','user_confirmation')
            if human:
                from .state import registered_regions
                try:region_ids=set(registered_regions(task))
                except (ValueError,KeyError,TypeError,OSError):region_ids=set()
            if human and isinstance(g.get('region_id'),str) and g['region_id'] in region_ids and isinstance(row,dict) and row and (not g.get('entity_id') or row.get('entity_id')==g['entity_id']):refs=['user-confirmed:'+g['region_id']]
        else:
            matches=[]
            for c in current:
                if not matching_goals(task,c['rule_id'],c.get('user_inputs',{}),g['id']):continue
                context=c.get('plan_context') or {}
                if g['inventory_scope']=='remaining' and (context.get('plan_id')!=task.get('inventory_plan_copy',{}).get('plan_id') or context.get('inventory_scope')!='remaining'):continue
                if g['inventory_scope']=='observed' and context.get('inventory_scope')=='remaining':continue
                matches.append(c)
            groups={}
            for c in matches:
                p=c['user_inputs'];common={k:v for k,v in p.items() if k!='product_id'}
                key=canonical([common,c.get('plan_context')])
                groups.setdefault(key,[]).append(c)
            for group in groups.values():
                if not set(g['rule_ids'])<={c['rule_id'] for c in group}:continue
                if not set(g['product_ids'])<={c['user_inputs'].get('product_id') for c in group}:continue
                refs=[c['run_id'] for c in group];break
            if not refs:reason='Missing requested rule/alternative, mismatched operands, plan identity, version or stale result.'
        statuses.append({'goal_id':g['id'],'kind':g['kind'],'user_quote':g['user_quote'],
                         'status':'SATISFIED' if refs else 'NEEDS_EVIDENCE','result_refs':sorted(set(refs)),
                         'reason':None if refs else reason})
    complete=bool(statuses) and spec.get('task_revision')==task['revision'] and all(g['status']=='SATISFIED' for g in statuses)
    return {'status':'REGISTERED_GOALS_SATISFIED' if complete else 'PARTIAL' if goals else 'UNSPECIFIED',
            'complete':complete,'goals':statuses,'missing_goal_ids':[g['goal_id'] for g in statuses if g['status']!='SATISFIED'],
            'completion_scope':'registered_user_anchored_goals','independently_verified':False,
            'semantic_exhaustiveness_verified':False,'task_revision':task['revision'],'snapshot_id':task['snapshot_id']}
