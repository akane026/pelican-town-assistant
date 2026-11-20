"""Declarative capability dependencies and release audits; never grant approvals."""
from __future__ import annotations
import copy
from .core import digest

GROUPS = ('entities','facts','relations','evidence','assets','occurrences','regions','observations','alignments')
CRITICAL = ('facts','relations','alignments')

# Domain representation contracts are not new game observations or approvals.
# Their basis must be explicitly retrieved into the active task before use.
FACT_UNIT_CONTRACTS={
    'growth_nights':{
        'definition':'一次有效生长夜晚是一次满足生长条件的夜间推进。基础生长时间的 days 可按这一计数解释，但不能保证任意经过的自然日数或推定具体收获日期；浇水条件必须由来源支持。',
        'basis_selectors':[{'kind':'fact','subject':'entity:Calendar','predicate':'watered_growth','unit':'condition','value':True}],
        'scope':'base_growth_progress_not_unconditional_calendar_dates'}}

def fact_unit_dependencies(body,fact_ids):
    from .core import ValidationError
    facts={r['id']:r for r in body.get('facts',[])}
    if not isinstance(fact_ids,list) or not 1<=len(fact_ids)<=8 or any(i not in facts for i in fact_ids):raise ValidationError('FACT_DEPENDENCIES_REQUIRE_CURRENT_BUNDLE_FACTS')
    definitions=[];selectors=[]
    for unit,contract in FACT_UNIT_CONTRACTS.items():
        targets=sorted(i for i in set(fact_ids) if facts[i].get('unit')==unit)
        if targets:
            definitions.append({'unit':unit,'target_fact_ids':targets,**copy.deepcopy(contract),'contract_hash':digest(contract)})
            selectors.extend(copy.deepcopy(contract['basis_selectors']))
    return {'unit_definitions':definitions,'selectors':selectors}


def _approved(row, approvals):
    if row.get('review_status') == 'conflicted':
        return False
    if approvals is not None:
        if isinstance(approvals, (set, frozenset, list, tuple)):
            return row['id'] in approvals
        decision = approvals.get(row['id'], {})
    else:
        decision = row.get('approval', {})
    return (decision.get('actor') == 'local_user' and decision.get('action') == 'approve'
            and bool(str(decision.get('reason', '')).strip()))


def record_dependencies(row):
    ids = []
    for key in ('support_fact_ids','support_relation_ids','support_alignment_ids','depends_on'):
        ids.extend(row.get(key, []))
    if row.get('target_kind') in ('fact','relation'):
        ids.append(row['target_id'])
    return list(dict.fromkeys(ids))


def _result(status, **kw):
    return {'status': status, **kw}


def _combine(op, children):
    statuses = [c['status'] for c in children]
    if not children:
        return _result('AVAILABLE' if op == 'all' else 'MISSING_KNOWLEDGE', children=[])
    if op == 'any' and 'AVAILABLE' in statuses:
        return _result('AVAILABLE', children=children, selected_branch=statuses.index('AVAILABLE'))
    if op == 'all' and all(s == 'AVAILABLE' for s in statuses):
        return _result('AVAILABLE', children=children)
    if op == 'all' and 'NOT_APPLICABLE' in statuses:
        return _result('NOT_APPLICABLE', children=children)
    relevant = [s for s in statuses if s != 'NOT_APPLICABLE']
    if not relevant:
        status = 'NOT_APPLICABLE'
    else:
        # OR retains viable missing-input/review branches; a broken alternative
        # does not make another valid branch unusable.
        order = (('NEEDS_INPUT','PENDING_REVIEW','MISSING_KNOWLEDGE','INVALID_DEPENDENCY')
                 if op == 'any' else
                 ('INVALID_DEPENDENCY','MISSING_KNOWLEDGE','PENDING_REVIEW','NEEDS_INPUT'))
        status = next((s for s in order if s in relevant), relevant[0])
    return _result(status, children=children)


def dependency_checker(domain, approvals=None):
    records = {r['id']: r for k in GROUPS for r in domain.get(k, [])}
    critical = {r['id'] for k in CRITICAL for r in domain.get(k, [])}
    group_ids={k:{r['id'] for r in domain.get(k,[])} for k in GROUPS}

    def check(record_id, stack=()):
        if record_id in stack:
            return _result('INVALID_DEPENDENCY', id=record_id, reason='DEPENDENCY_CYCLE', cycle=[*stack,record_id])
        row = records.get(record_id)
        if row is None:
            return _result('MISSING_KNOWLEDGE', id=record_id, reason='MISSING_DEPENDENCY_RECORD')
        if row.get('method') == 'source_grounded_category_join' and len(row.get('support_fact_ids',[]))<2:
            return _result('INVALID_DEPENDENCY', id=record_id, reason='DERIVATION_WITHOUT_INPUTS')
        if row.get('method')=='stage_sequence_illustration/v1' and len(row.get('support_alignment_ids',[]))<2:
            return _result('INVALID_DEPENDENCY',id=record_id,reason='ILLUSTRATION_WITHOUT_STATE_SUPPORTS')
        if row.get('derivation_inputs_incomplete'):
            return _result('INVALID_DEPENDENCY',id=record_id,reason='DERIVATION_INPUTS_INCOMPLETE')
        for field in ('support_fact_ids','support_relation_ids','support_alignment_ids','depends_on'):
            if field in row and (not isinstance(row[field],list) or any(not isinstance(i,str) for i in row[field])):
                return _result('INVALID_DEPENDENCY',id=record_id,reason='INVALID_DEPENDENCY_IDS',field=field)
            expected={'support_fact_ids':'facts','support_relation_ids':'relations','support_alignment_ids':'alignments'}.get(field)
            if expected and any(i in records and i not in group_ids[expected] for i in row.get(field,[])):
                return _result('INVALID_DEPENDENCY',id=record_id,reason='DEPENDENCY_TYPE_MISMATCH',field=field)
        if record_id in critical and row.get('review_status') == 'conflicted':
            return _result('INVALID_DEPENDENCY', id=record_id, reason='CONFLICTED_RECORD')
        children = [check(i, (*stack,record_id)) for i in record_dependencies(row)]
        if record_id in critical and not _approved(row, approvals):
            children.append(_result('PENDING_REVIEW', id=record_id, reason='RECORD_REVIEW_REQUIRED'))
        result = _combine('all', children)
        return {**result, 'id':record_id}
    return check


def audit_release_dependencies(domain, approved_ids):
    check = dependency_checker(domain, approved_ids)
    critical = {r['id'] for k in CRITICAL for r in domain.get(k, [])}
    rows = [check(i) for i in sorted(set(approved_ids) & critical)]
    invalid = [r for r in rows if r['status'] != 'AVAILABLE']
    return {'status':'PASS' if not invalid else 'BLOCKED', 'checked':len(rows),
            'records':rows, 'blocked_ids':[r['id'] for r in invalid]}


def assess_capabilities(domain, capabilities, *, approvals=None, rule_reviews=None,
                        params=None, snapshot_id=None, task_revision=None):
    """Evaluate all/any/when dependency expressions without accessing candidate stores.

    A leaf is {record: id}, {selector: {kind:'fact', subject:'$entity_id', ...}},
    {rule: {id:'sale_value', fingerprint:'...'}}, or {input:'quantity'}.
    Conditional form: {when:{quality:'normal'}, then:expr, else:expr?}.
    capabilities is [{id, dependencies:expr, description?:str}].
    """
    params = params or {}; rule_reviews = rule_reviews or {}
    check = dependency_checker(domain, approvals)
    class MissingInput(Exception):pass
    def resolve(value):
        if isinstance(value, str) and value.startswith('$'):
            name = value[1:]
            if name not in params or params[name] is None:
                raise MissingInput(name)
            return params[name]
        if isinstance(value, dict):return {k:resolve(v) for k,v in value.items()}
        if isinstance(value, list):return [resolve(v) for v in value]
        return value
    def contains(row, wanted):
        return all(k in row and (contains(row[k],v) if isinstance(v,dict) and isinstance(row[k],dict)
                                else row[k] == v) for k,v in wanted.items())
    def evaluate(expr):
        if not isinstance(expr, dict) or len(set(expr) & {'all','any','when','record','selector','rule','input'}) != 1:
            return _result('INVALID_DEPENDENCY',reason='INVALID_DEPENDENCY_EXPRESSION')
        try:
            if 'all' in expr or 'any' in expr:
                op = 'all' if 'all' in expr else 'any'
                if not isinstance(expr[op],list):return _result('INVALID_DEPENDENCY',reason='DEPENDENCY_CHILDREN_MUST_BE_LIST')
                return _combine(op,[evaluate(c) for c in expr[op]])
            if 'input' in expr:
                name=expr['input']
                return _result('AVAILABLE' if name in params and params[name] is not None else 'NEEDS_INPUT',input=name)
            if 'when' in expr:
                conditions=resolve(expr['when'])
                missing=[k for k in conditions if k not in params or params[k] is None]
                if missing:return _result('NEEDS_INPUT',missing_inputs=missing,conditions=conditions)
                if contains(params,conditions):return {**evaluate(expr['then']),'conditions':conditions}
                return evaluate(expr['else']) if 'else' in expr else _result('NOT_APPLICABLE',conditions=conditions)
            if 'record' in expr:return check(resolve(expr['record']))
            if 'rule' in expr:
                spec=expr['rule']; spec={'id':spec} if isinstance(spec,str) else spec
                spec=resolve(spec); review=rule_reviews.get(spec['id'],{})
                valid=(review.get('status')=='approved_human' and bool(spec.get('fingerprint'))
                       and review.get('fingerprint')==spec['fingerprint'])
                return _result('AVAILABLE' if valid else 'PENDING_REVIEW',rule_id=spec['id'],
                               reason=None if valid else 'RULE_REVIEW_OR_FINGERPRINT_REQUIRED')
            selector=resolve(expr['selector']);kind=selector.pop('kind',None)
            group={'fact':'facts','relation':'relations','entity':'entities','alignment':'alignments'}.get(kind)
            if not group:return _result('INVALID_DEPENDENCY',reason='UNKNOWN_SELECTOR_KIND')
            if '__context' in selector:
                from .rules import matches_selector
                matches=[r for r in domain.get(group,[]) if matches_selector(r,selector)]
                if not matches:
                    identity={k:v for k,v in selector.items() if k!='__context'}
                    candidates=[r for r in domain.get(group,[]) if matches_selector(r,identity)]
                    if candidates:
                        context=selector['__context'];metadata={'game_version','knowledge_scope','derivation','ordinal','rule_version','sequence_basis'}
                        missing=sorted({k for r in candidates for k in (r.get('conditions') or {})
                                        if k not in metadata and k not in context})
                        if missing:return _result('NEEDS_INPUT',missing_inputs=missing,selector={'kind':kind,**selector})
                        return _result('NOT_APPLICABLE',reason='CONDITIONS_NOT_SATISFIED',selector={'kind':kind,**selector})
            else:matches=[r for r in domain.get(group,[]) if contains(r,selector)]
            return {**_combine('any',[check(r['id']) for r in matches]),'selector':{'kind':kind,**selector}}
        except MissingInput as exc:return _result('NEEDS_INPUT',missing_inputs=[str(exc)])
        except (KeyError,TypeError,AttributeError) as exc:
            return _result('INVALID_DEPENDENCY',reason='INVALID_EXPRESSION',detail=str(exc))
    rows=[]
    for capability in capabilities:
        result=evaluate(copy.deepcopy(capability['dependencies']))
        rows.append({'id':capability['id'],'description':capability.get('description',''),**result})
    return {'schema':'capability-report/v1','snapshot_id':snapshot_id,'task_revision':task_revision,
            'params_hash':digest(params),'capabilities':rows,'status':'AVAILABLE' if rows and all(r['status']=='AVAILABLE' for r in rows) else 'PARTIAL',
            'limitations':['Capability checks do not grant human approval or prove natural-language task completeness.']}
