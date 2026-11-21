"""Versioned evaluation tooling; candidates and model judgments are never human gold.

The execution side receives public input only. Expected goals are read later by
the scorer, and are never inferred from runtime TaskSpec or calculator outputs.
No model client is created unless the caller explicitly selects online execution.
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import json
import re
import time
import uuid
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .core import ROOT, ValidationError, canonical, digest, file_hash, now, read, write
from .evidence_payload import BUDGET_DEFINITION, BUDGET_DEFINITION_HASH, chars as payload_chars

SCHEMA = 'stardew/post-midterm-evaluation/v1'
METHODS = ('B', 'BQ', 'C', 'D', 'product')
BAD_TERMINAL = {'ERROR', 'MODEL_ERROR', 'TOOL_ERROR', 'BUDGET_STOP',
                'ANSWER_VALIDATION_FAILED', 'INVALID_MODEL_OUTPUT', 'REPEATED_FAILURE_STOP',
                'STATE_CHANGED', 'CANCELLED', 'EXECUTION_ERROR', 'API_ERROR', 'INVALID_JSON', 'BLOCKED'}


def local_path(value, root=ROOT):
    p = Path(value)
    p = (Path(root) / p).resolve() if not p.is_absolute() else p.resolve()
    if not p.is_relative_to(Path(root).resolve()):
        raise ValidationError('EVALUATION_PATH_OUTSIDE_ROOT')
    return p


def read_rows(path):
    p = Path(path)
    return [json.loads(line) for line in p.read_text(encoding='utf-8').splitlines() if line.strip()] if p.suffix == '.jsonl' else read(p)


def exclusive_write(path, data):
    """Do not replace a prior frozen protocol, review export or run artifact."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n'
    try:
        with p.open('x',encoding='utf-8',newline='\n') as stream:
            stream.write(encoded)
    except FileExistsError:
        if p.read_text(encoding='utf-8') != encoded:
            raise ValidationError('EVALUATION_OUTPUT_ALREADY_EXISTS')
    return str(p)


def load_protocol(path, *, root=ROOT):
    p = local_path(path, root)
    protocol = read(p)
    if protocol.get('schema') != SCHEMA:
        raise ValidationError('EVALUATION_SCHEMA')
    cases_path = local_path(protocol['cases_path'], root)
    sources_path = local_path(protocol['sources_path'], root)
    return {'protocol': protocol, 'cases': read_rows(cases_path), 'sources': read_rows(sources_path),
            'root': str(Path(root).resolve()), 'protocol_path': str(p),
            'hashes': {'protocol': file_hash(p), 'cases': file_hash(cases_path), 'sources': file_hash(sources_path)}}


def case_hash(case):
    return digest(case)


def _assets(bundle):
    return {s['id']: s for s in bundle['sources'] if s.get('kind') in ('real_screenshot', 'synthetic_image', 'wiki_template')}


def validate_protocol(bundle):
    errors, blockers = [], []
    cases, sources, protocol = bundle['cases'], bundle['sources'], bundle['protocol']
    ids = [c.get('id') for c in cases]
    if not cases or None in ids or len(ids) != len(set(ids)):
        errors.append('EMPTY_OR_DUPLICATE_CASE_IDS')
    if any(not isinstance(cid, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', cid) for cid in ids):
        errors.append('UNSAFE_CASE_ID')
    source_ids = [s.get('id') for s in sources]
    if None in source_ids or len(source_ids) != len(set(source_ids)):
        errors.append('DUPLICATE_SOURCE_IDS')
    src = {s['id']: s for s in sources}
    group_splits = {}
    byte_splits = {}
    for s in sources:
        if s.get('kind') not in ('real_screenshot', 'synthetic_image', 'wiki_template'):
            continue
        # A known entity's Wiki sprite is a legitimate reference gallery. Only
        # capture families and query-byte duplicates determine query leakage.
        if s['kind'] != 'wiki_template':
            group = s.get('capture_group')
            if not group:
                errors.append('IMAGE_CAPTURE_GROUP_MISSING:' + s['id'])
            group_splits.setdefault(group, set()).add(s.get('split'))
            byte_splits.setdefault(s.get('sha256'), set()).add(s.get('split'))
        if not s.get('path') or not s.get('sha256'):
            blockers.append('IMAGE_FILE_PENDING:' + s['id'])
        else:
            try:
                p = local_path(s['path'], bundle['root'])
                if not p.is_file() or file_hash(p) != s['sha256']:
                    errors.append('IMAGE_BYTES_MISMATCH:' + s['id'])
            except ValueError:
                errors.append('IMAGE_PATH_INVALID:' + s['id'])
        if s['kind'] == 'synthetic_image' and s.get('claim_scope') == 'independent_real_screenshot':
            errors.append('SYNTHETIC_REAL_CLAIM:' + s['id'])
    if any(len(v - {None}) > 1 for v in group_splits.values()):
        errors.append('CAPTURE_GROUP_SPLIT_LEAKAGE')
    if any(k and len(v - {None}) > 1 for k, v in byte_splits.items()):
        errors.append('QUERY_BYTES_SPLIT_LEAKAGE')
    for c in cases:
        prefix = str(c.get('id')) + ':'
        turns, goals = c.get('turns', []), c.get('expected_goals', [])
        if not turns or any(not isinstance(t.get('message'), str) or not t['message'].strip() for t in turns):
            errors.append(prefix + 'MISSING_TURNS')
        if not goals or len({g.get('id') for g in goals}) != len(goals):
            errors.append(prefix + 'MISSING_OR_DUPLICATE_EXPECTED_GOALS')
        if c.get('expected_origin') not in ('human_authored', 'assistant_authored_pending_review', 'independent_reference_implementation'):
            errors.append(prefix + 'EXPECTED_ORIGIN_REQUIRED')
        if c.get('expected_origin') in ('runtime_taskspec', 'calculator_output', 'model_self_judgment'):
            errors.append(prefix + 'SELF_DERIVED_EXPECTATION')
        if c.get('independence') == 'post_implementation_development' and c.get('claim_scope') == 'blind_test':
            errors.append(prefix + 'DEVELOPMENT_SET_CLAIMED_BLIND')
        for g in goals:
            if type(g.get('turn')) is not int or not 0 <= g['turn'] < len(turns):
                errors.append(prefix + 'GOAL_TURN_OUT_OF_RANGE')
            if g.get('kind') not in ('calculation', 'status', 'knowledge', 'state'):
                errors.append(prefix + 'GOAL_KIND')
            if g.get('kind') == 'calculation' and (not g.get('rule_id') or not isinstance(g.get('expected_outputs'), dict)):
                errors.append(prefix + 'CALCULATION_GOAL_SCHEMA')
            if g.get('kind') == 'status' and not g.get('allowed_statuses'):
                errors.append(prefix + 'STATUS_GOAL_SCHEMA')
        for i, t in enumerate(turns):
            if any(k.startswith('expected') or k in ('gold', 'answer', 'target_labels') for k in t):
                errors.append(prefix + 'EXPECTED_DATA_IN_PUBLIC_TURN')
            for image_id in t.get('image_ids', []):
                image = src.get(image_id)
                if not image:
                    blockers.append(prefix + 'MISSING_IMAGE:' + image_id)
                elif image.get('kind') == 'wiki_template' and c.get('claim_scope') == 'independent_real_screenshot':
                    errors.append(prefix + 'WIKI_TEMPLATE_AS_REAL_QUERY')
            if t.get('requires_image') and not t.get('image_ids'):
                blockers.append(prefix + f'TURN_{i}_IMAGE_PENDING')
            if c.get('identity_visibility') == 'hidden':
                text = t['message'].casefold()
                if any(label.casefold() in text for label in c.get('hidden_identity_labels', []) if label):
                    errors.append(prefix + 'IDENTITY_LABEL_IN_QUERY')
        if not c.get('source_refs') and c.get('category') not in ('unsupported', 'visual_unknown', 'missing_input'):
            blockers.append(prefix + 'SOURCE_REFERENCE_PENDING')
        for ref in c.get('source_refs', []):
            if ref not in src:
                errors.append(prefix + 'UNKNOWN_SOURCE:' + ref)
    if protocol.get('budgets') != {'pages': 5, 'candidate_entities': 30, 'edge_reads': 120, 'hops': 3,
                                   'final_records': 12, 'images': 4, 'unicode_chars': 6000}:
        blockers.append('BUDGET_ADAPTER_REQUIRES_VERIFICATION')
    return {'status': 'FAIL' if errors else 'VALIDATED_PENDING_REVIEW', 'errors': sorted(set(errors)),
            'formal_blockers': sorted(set(blockers)), 'case_count': len(cases), 'hashes': bundle['hashes'],
            'candidate_inputs_ready': not errors and not blockers,
            'formal_ready': False, 'gold_reviewed_here': 0,
            'independence_counts': dict(Counter(c.get('independence', 'unknown') for c in cases))}


def export_review(bundle, output):
    validation = validate_protocol(bundle)
    if validation['errors']:
        raise ValidationError('INVALID_EVALUATION_PROTOCOL:' + ','.join(validation['errors']))
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    template = {'schema': SCHEMA, 'review_kind': 'evaluation_gold', 'dataset_hash': bundle['hashes']['cases'],
                'protocol_hash': bundle['hashes']['protocol'], 'source_hash': bundle['hashes']['sources'],
                'reviews': [{'case_id': c['id'], 'case_hash': case_hash(c), 'decision': None, 'actor_kind': None,
                             'actor_id': None, 'reviewed_at': None, 'reason': None, 'review_origin': None,
                             'goals_checked': [g['id'] for g in c['expected_goals']]} for c in bundle['cases']]}
    exclusive_write(out / 'gold_review_template.json', template)
    lines = ['# 完整逐轮评测待审清单', '', '本清单是实现后编写的开发/候选材料，不是已批准金标准。',
             '审核知识与审核评测标准是两种独立动作；此文件没有批准任何一项。', '']
    for c in bundle['cases']:
        lines += [f"## {c['id']} · {c['category']}", '', f"独立性：{c['independence']}；划分：{c['split']}", '']
        for i, t in enumerate(c['turns']):
            lines += [f'### 用户第 {i + 1} 轮', '', t['message'], '',
                      '图片：' + (', '.join(t.get('image_ids', [])) or ('待提供' if t.get('requires_image') else '无')), '']
            for image_id in t.get('image_ids', []):
                image = _assets(bundle).get(image_id, {})
                if image.get('path'):
                    lines += [f"![待审核查询区域 {image_id}]({local_path(image['path'], bundle['root'])})", '',
                              f"原截图族：{image.get('capture_group')}；用途：{image.get('claim_scope')}；标签仍需人工核对。", '']
            for g in c['expected_goals']:
                if g['turn'] == i:
                    lines += [f"预期目标 {g['id']}：{g.get('description', '')}", '',
                              '```json', json.dumps(g, ensure_ascii=False, indent=2), '```', '']
        lines += ['来源：' + ', '.join(c.get('source_refs', [])), '', '人工决定／理由：待填写', '']
    target = out / '完整逐轮待审目录.md'
    content = '\n'.join(lines) + '\n'
    if target.exists() and target.read_text(encoding='utf-8') != content:
        raise ValidationError('EVALUATION_OUTPUT_ALREADY_EXISTS')
    target.write_text(content,encoding='utf-8',newline='\n')
    return {'status': 'PENDING_HUMAN', 'directory': str(out), 'case_count': len(bundle['cases']),
            'validation': validation, 'gold_reviewed': 0}


def _approved_review(review):
    try:
        datetime.datetime.fromisoformat(review.get('reviewed_at', '').replace('Z', '+00:00'))
    except (ValueError, AttributeError, TypeError):
        return False
    return (review.get('decision') == 'approve' and review.get('actor_kind') == 'human'
            and review.get('review_origin') == 'explicit_human_review'
            and isinstance(review.get('actor_id'), str) and bool(review['actor_id'].strip())
            and review['actor_id'].strip().casefold() not in ('assistant', 'codex', 'model', 'synthetic')
            and isinstance(review.get('reason'), str) and bool(review['reason'].strip())
            and not review.get('synthetic', False))


def _knowledge_gate(manifest_path, required_rules):
    from .knowledge import Snapshot
    from .rules import rule_audit
    m = read(manifest_path)
    if m.get('release_status') != 'released':
        raise ValidationError('FORMAL_KNOWLEDGE_NOT_RELEASED')
    snapshot = Snapshot(m['snapshot_id'])
    if snapshot.manifest != m:
        raise ValidationError('FORMAL_KNOWLEDGE_MANIFEST_MISMATCH')
    audits = {key: rule_audit(key) for key in required_rules}
    if any(row.get('status') != 'approved_human' for row in audits.values()):
        raise ValidationError('FORMAL_RULE_REVIEW_PENDING')
    return {'snapshot_id': snapshot.id, 'manifest_hash': file_hash(manifest_path),
            'rule_review_hash': digest(audits), 'required_rules': sorted(required_rules)}


def _validate_gold_reviews(bundle, gold_reviews):
    reviews = read(gold_reviews)
    if reviews.get('review_kind') != 'evaluation_gold' or reviews.get('dataset_hash') != bundle['hashes']['cases'] \
       or reviews.get('protocol_hash') != bundle['hashes']['protocol'] or reviews.get('source_hash') != bundle['hashes']['sources']:
        raise ValidationError('GOLD_REVIEW_HASH_MISMATCH')
    rows = reviews.get('reviews', [])
    if len({r.get('case_id') for r in rows}) != len(rows):
        raise ValidationError('DUPLICATE_GOLD_REVIEWS')
    by_id = {r['case_id']: r for r in rows}
    for c in bundle['cases']:
        r = by_id.get(c['id'], {})
        if not _approved_review(r) or r.get('case_hash') != case_hash(c) or set(r.get('goals_checked', [])) != {g['id'] for g in c['expected_goals']}:
            raise ValidationError('INDEPENDENT_GOLD_REVIEW_PENDING:' + c['id'])


def freeze_protocol(bundle, gold_reviews, knowledge_manifest, output):
    validation = validate_protocol(bundle)
    if validation['errors'] or validation['formal_blockers']:
        raise ValidationError('FORMAL_PROTOCOL_INCOMPLETE')
    _validate_gold_reviews(bundle, gold_reviews)
    rules = {g['rule_id'] for c in bundle['cases'] for g in c['expected_goals'] if g.get('rule_id')}
    knowledge = _knowledge_gate(knowledge_manifest, rules)
    frozen = {'schema': SCHEMA, 'status': 'FROZEN_REVIEWED_PROTOCOL', 'hashes': bundle['hashes'],
              'gold_review_hash': file_hash(gold_reviews), 'gold_reviews_path': str(Path(gold_reviews).resolve()),
              'knowledge_manifest_path': str(Path(knowledge_manifest).resolve()), 'knowledge': knowledge,
              'case_hashes': {c['id']: case_hash(c) for c in bundle['cases']}, 'created_at': now(),
              'claim_scope': 'reviewed_development_submission_set' if any(c['independence'] == 'post_implementation_development' for c in bundle['cases']) else 'protocol_declared_holdout',
              'human_review_note': 'Records supplied by a human are required; the tool does not independently authenticate a person.'}
    frozen['freeze_id'] = digest(frozen)
    exclusive_write(output, frozen)
    return frozen


def verify_frozen(bundle, path):
    frozen = read(path)
    body = {k: v for k, v in frozen.items() if k != 'freeze_id'}
    if frozen.get('status') != 'FROZEN_REVIEWED_PROTOCOL' or frozen.get('freeze_id') != digest(body) or frozen.get('hashes') != bundle['hashes']:
        raise ValidationError('FROZEN_PROTOCOL_CHANGED')
    if file_hash(frozen['gold_reviews_path']) != frozen['gold_review_hash']:
        raise ValidationError('GOLD_REVIEW_CHANGED')
    _validate_gold_reviews(bundle, frozen['gold_reviews_path'])
    knowledge = _knowledge_gate(frozen['knowledge_manifest_path'], frozen['knowledge']['required_rules'])
    if knowledge != frozen['knowledge']:
        raise ValidationError('KNOWLEDGE_OR_RULE_REVIEW_CHANGED')
    return frozen


def live_agent_factory(*, tasks, method, run_dir, budgets):
    if method == 'product':
        raise ValidationError('PRODUCT_BASELINE_ADAPTER_REQUIRED')
    from .agent import Agent
    from .retrieval import Retriever

    class MethodAgent(Agent):
        def dispatch(self, name, args, task_id, snapshot, latest_message):
            if name == 'retrieve_knowledge' and Retriever(snapshot).budgets != budgets:
                raise ValidationError('RUNTIME_RETRIEVAL_BUDGET_MISMATCH')
            return super().dispatch(name, args, task_id, snapshot, latest_message)

    return MethodAgent(tasks=tasks, retrieval_method=method)


def _code_fingerprint():
    files = list((ROOT / 'stardew_agent').glob('*.py')) + list((ROOT / 'verification').glob('*.py'))
    files += list((ROOT / 'scripts').glob('*.py'))
    files += list((ROOT / 'configs').glob('*.json')) + [ROOT / 'evaluation/protocols/v3.json']
    return {str(p.relative_to(ROOT)): file_hash(p) for p in sorted(set(files)) if p.is_file()}


def _runtime_model_identity(agent, synthetic):
    if synthetic:
        return {'kind': 'synthetic_fixture', 'adapter': type(agent).__module__ + '.' + type(agent).__qualname__}
    wrapper = getattr(agent, 'client', None)
    client = getattr(wrapper, 'client', wrapper)
    config = getattr(client, 'config', {})
    # Only these public configuration values are read. Never serialize config,
    # environment variables, credentials, headers or the client object.
    raw_url = config.get('CHATECNU_BASE_URL') or ''
    parsed = urlsplit(raw_url)
    host = parsed.hostname or ''
    if parsed.port:
        host += ':' + str(parsed.port)
    safe_url = urlunsplit((parsed.scheme, host, parsed.path, '', ''))
    result = {'kind': 'configured_live_client', 'base_url': safe_url,
              'text_model': config.get('CHATECNU_MODEL'), 'vision_model': config.get('CHATECNU_VISION_MODEL')}
    if not safe_url or not result['text_model'] or not result['vision_model']:
        result['kind'] = 'unavailable'
    return result


def _turn_images(bundle, turn, tasks, task_id):
    """Import user-visible bytes only; source labels and expected IDs stay offline."""
    assets = _assets(bundle)
    from .online_vision import ImageStore
    store = ImageStore()
    task = tasks.get(task_id)
    registered, uploads = list(task['selected_regions']), list(task['uploaded_images'])
    for image_id in turn.get('image_ids', []):
        s = assets.get(image_id)
        if not s or not s.get('path') or not s.get('sha256'):
            raise ValidationError('MISSING_VISUAL_INPUT')
        p = local_path(s['path'], bundle['root'])
        if not p.is_file() or file_hash(p) != s['sha256']:
            raise ValidationError('VISUAL_INPUT_BYTES_MISMATCH')
        uploaded = store.upload(p.read_bytes(), task_id)
        uploads.append(uploaded)
        region = store.region(uploaded['image_id'], task_id, turn.get('roi', [0, 0, 1, 1]))
        registered.append(region)
    task = tasks.update(task_id, task['revision'], {})
    tasks.save_runtime(task_id, task['revision'], uploaded_images=uploads, selected_regions=registered)


def stage_metrics(answer):
    retrievals, supplements, tools, model_calls = [], [], [], set()
    all_tool_message_chars=0;receipts=[]
    for event in answer.get('tool_events', []):
        tools.append(event.get('tool'))
        if event.get('model_call_number') is not None:
            model_calls.add(event['model_call_number'])
        result = event.get('result') or {}
        all_tool_message_chars+=payload_chars(result.get('model_payload',result))
        if result.get('budget_receipt'):receipts.append(result['budget_receipt'])
        trace = result.get('trace') or {}
        if event.get('tool') in ('retrieve_knowledge', 'retrieve_text', 'source_rag'):
            if event.get('tool') == 'source_rag' and not trace:
                baseline = answer.get('baseline', {})
                trace = {'selected_ids': result.get('selected_ids', []),
                         'budget_used': {'source_records_scored': baseline.get('source_records_scored'),
                                         'unicode_chars': baseline.get('evidence_characters'),
                                         'images': len(baseline.get('images', []))},
                         'method': baseline.get('method'), 'record_kind': 'original_source_chunk'}
            retrievals.append(trace)
        elif event.get('tool') in ('fetch_dependencies','fetch_fact_dependencies'):
            supplements.append(trace or {'status': result.get('status'), 'missing': result.get('missing_dependencies', [])})
    first = retrievals[0] if retrievals else None
    return {'initial_retrieval': {'trace': first, 'selected_ids': first.get('selected_ids', []) if first else [],
                                  'budget_used': first.get('budget_used', {}) if first else {},
                                  'budget_receipt':next((r for r in receipts if r.get('phase')=='initial'),None)},
            'additional_retrievals': retrievals[1:],
            'supplementation': {'rounds': len(supplements), 'records_examined': sum(t.get('records_examined', 0) for t in supplements),
                                'seconds': sum(t.get('total_seconds', 0) for t in supplements), 'traces': supplements},
            'final_task': {'status': answer.get('status'), 'task_revision': answer.get('task_revision'),
                           'calculation_count': len(answer.get('calculation_traces', [])), 'full_goal_success': None},
            'cost': {'tool_calls': len(tools), 'tool_seconds': sum(e.get('elapsed_seconds', 0) for e in answer.get('tool_events', [])),
                     'cumulative_model_visible_chars':all_tool_message_chars,'tool_message_character_proxy':all_tool_message_chars,
                     'evidence_payload_receipts':receipts,'budget_definition_hash':BUDGET_DEFINITION_HASH,
                     'character_proxy_scope':'All produced tool result/model_payload JSON, including get_evidence/calculation/discovery; excludes system prompts, repeated history, binary images and tokens.',
                     'observed_agent_model_call_ids': sorted(model_calls, key=str), 'model_calls_lower_bound': len(model_calls),
                     'reported_model_requests': answer.get('baseline', {}).get('model_requests'),
                     'elapsed_seconds': answer.get('elapsed_seconds'), 'tokens': None, 'money': None,
                     'note': 'Model calls observed in tool events are a lower bound; absent usage/cost is unknown, never zero.'}}


def budget_contract_errors(answer, limit):
    errors=[];bundles={}
    supplement_tools={'fetch_dependencies','fetch_fact_dependencies'}
    def rows(data,key):return {r['id']:r for r in data.get(key,[]) if isinstance(r,dict) and 'id' in r}
    def projection(payload):
        return {'seen_records':{**rows(payload,'facts'),**rows(payload,'relations')},'seen_evidence':rows(payload,'evidence_refs'),
                'seen_entities':rows(payload,'entities'),'seen_assets':{r['asset_id']:r for r in payload.get('image_evidence',[]) if isinstance(r,dict) and 'asset_id' in r}}
    for index,event in enumerate(answer.get('tool_events',[])):
        tool=event.get('tool');supplement=tool in supplement_tools
        if tool not in {'retrieve_knowledge','retrieve_text','source_rag'}|supplement_tools:continue
        result=event.get('result') or {}
        if result.get('status') in ('TOOL_ERROR','ERROR'):continue
        payload=result.get('model_payload');receipt=result.get('budget_receipt',{})
        if supplement and result.get('status') in ('DEPENDENCIES_ALREADY_PRESENT','INCOMPLETE_DEPENDENCY_DISCOVERY') and payload is None:
            if any(result.get(k) for k in ('facts','relations','evidence_refs')):errors.append(f'{index}:HIDDEN_NOOP_RECORDS')
            continue
        if not isinstance(payload,dict):errors.append(f'{index}:MISSING_MODEL_PAYLOAD');continue
        actual=payload_chars(payload)
        if actual>limit:errors.append(f'{index}:SUPPLEMENT_VISIBLE_BUDGET_EXCEEDED' if supplement else f'{index}:INITIAL_VISIBLE_BUDGET_EXCEEDED')
        if receipt.get('model_visible_evidence_chars')!=actual:errors.append(f'{index}:VISIBLE_CHARACTER_RECEIPT_MISMATCH')
        if receipt.get('budget_definition_hash')!=BUDGET_DEFINITION_HASH:errors.append(f'{index}:BUDGET_DEFINITION_MISMATCH')
        if tool=='retrieve_knowledge' or supplement:
            trace=result.get('trace',{});visible=projection(payload)
            actual_ids={r['id'] for k in ('facts','relations') for r in result.get(k,[])}
            visible_ids=set(visible['seen_records']);expected={k:dict(v) for k,v in visible.items()}
            if supplement:
                parent=bundles.get(trace.get('parent_bundle_id'))
                if parent is None:errors.append(f'{index}:UNSEEN_SUPPLEMENT_PARENT')
                else:
                    for key in expected:
                        if set(parent[key])&set(visible[key]):errors.append(f'{index}:DUPLICATE_SUPPLEMENT_VISIBLE_RECORDS:{key}')
                        expected[key]={**parent[key],**visible[key]}
                    if receipt.get('cumulative_model_visible_evidence_chars')!=parent['cumulative']+actual:errors.append(f'{index}:CUMULATIVE_VISIBLE_CHARACTER_MISMATCH')
                    if set(payload.get('already_seen_record_refs',[]))!=set(parent['seen_records']) or set(payload.get('already_seen_evidence_refs',[]))!=set(parent['seen_evidence']):errors.append(f'{index}:ALREADY_SEEN_REFERENCE_MISMATCH')
                if visible_ids!=set(trace.get('added_ids',[])) or actual_ids!=set(trace.get('selected_ids',[])) or actual_ids!=set(expected['seen_records']):errors.append(f'{index}:HIDDEN_OR_MISMATCHED_SUPPLEMENT_RECORDS')
            elif actual_ids!=visible_ids or actual_ids!=set(trace.get('selected_ids',[])):
                errors.append(f'{index}:HIDDEN_OR_MISMATCHED_INITIAL_RECORDS')
            for key in ('seen_records','seen_evidence','seen_entities','seen_assets'):
                if set(trace.get('model_visibility',{}).get(key,[]))!=set(expected[key]):errors.append(f'{index}:VISIBLE_CLOSURE_MISMATCH:{key}')
            # Server full rows must preserve the content actually shown earlier
            # or in this payload, not merely reuse an already-visible ID.
            server={'seen_records':{**rows(result,'facts'),**rows(result,'relations')},'seen_evidence':rows(result,'evidence_refs')}
            for key,full in server.items():
                if set(full)!=set(expected[key]):errors.append(f'{index}:FULL_CLOSURE_MISMATCH:{key}')
                elif any(any(full[rid].get(k)!=v for k,v in row.items()) for rid,row in expected[key].items()):errors.append(f'{index}:VISIBLE_CONTENT_MISMATCH:{key}')
            expected['cumulative']=receipt.get('cumulative_model_visible_evidence_chars',actual)
            bundles[result.get('bundle_id')]=expected
    return errors


def run_cases(bundle, output, *, snapshot_id=None, method='D', mode='exploratory', case_ids=None,
              online=False, frozen_path=None, agent_factory=None, live_factory=None,
              image_preparer=None, comparison_family=None):
    if method not in METHODS or mode not in ('exploratory', 'formal'):
        raise ValidationError('EVALUATION_RUN_MODE')
    validation = validate_protocol(bundle)
    if validation['errors']:
        raise ValidationError('INVALID_EVALUATION_PROTOCOL')
    synthetic = agent_factory is not None
    if agent_factory is not None and live_factory is not None:
        raise ValidationError('EVALUATION_FACTORY_CONFLICT')
    comparison_family = comparison_family or ('product_workflow' if method == 'product' else 'structure_ablation')
    if comparison_family not in ('product_workflow', 'structure_ablation') or (method == 'product' and comparison_family != 'product_workflow'):
        raise ValidationError('EVALUATION_COMPARISON_FAMILY')
    if method not in bundle['protocol']['comparison_families'][comparison_family]['methods']:
        raise ValidationError('METHOD_NOT_IN_COMPARISON_FAMILY')
    if mode == 'formal' and synthetic:
        raise ValidationError('SYNTHETIC_AGENT_CANNOT_RUN_FORMAL')
    if mode == 'formal' and method == 'product':
        raise ValidationError('PRODUCT_FORMAL_PROTOCOL_NOT_APPROVED')
    frozen = verify_frozen(bundle, frozen_path) if mode == 'formal' and frozen_path else None
    if mode == 'formal' and frozen is None:
        raise ValidationError('FORMAL_FREEZE_REQUIRED')
    if not online and not synthetic:
        raise ValidationError('EXPLICIT_ONLINE_OPT_IN_REQUIRED')
    snapshot_id = snapshot_id or (frozen['knowledge']['snapshot_id'] if frozen else bundle['protocol']['knowledge_snapshot_id'])
    if frozen and snapshot_id != frozen['knowledge']['snapshot_id']:
        raise ValidationError('FORMAL_SNAPSHOT_MISMATCH')
    selected = set(case_ids or [c['id'] for c in bundle['cases']])
    if not selected <= {c['id'] for c in bundle['cases']}:
        raise ValidationError('UNKNOWN_EVALUATION_CASE')
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'run.json').exists():
        raise ValidationError('EVALUATION_OUTPUT_ALREADY_EXISTS')
    from .state import TaskStore
    tasks = TaskStore(out / 'tasks.sqlite3')
    factory = agent_factory or live_factory or live_agent_factory
    agent = factory(tasks=tasks, method=method, run_dir=out, budgets=bundle['protocol']['budgets'])
    code_before = _code_fingerprint()
    model_identity = _runtime_model_identity(agent, synthetic)
    exclusive_write(out / 'code_manifest.json', code_before)
    rows = [];budget_violations=[]
    for case in bundle['cases']:
        if case['id'] not in selected:
            continue
        task = tasks.create(snapshot_id, 'released' if mode == 'formal' else 'candidate_diagnostic')
        row = {'case_id': case['id'], 'case_hash': case_hash(case), 'task_id': task['task_id'], 'turns': [],
               'status': 'EXECUTED', 'formal_success': None}
        for index, turn in enumerate(case['turns']):
            start = time.perf_counter()
            before = tasks.get(task['task_id'])
            try:
                if turn.get('requires_image') and not turn.get('image_ids'):
                    raise ValidationError('MISSING_VISUAL_INPUT')
                if turn.get('image_ids'):
                    (image_preparer or _turn_images)(bundle, turn, tasks, task['task_id'])
                answer = agent.run(task['task_id'], turn['message'])
                if not isinstance(answer, dict):
                    raise ValidationError('EVALUATION_AGENT_RESPONSE_SCHEMA')
                after = tasks.get(task['task_id'])
                if not synthetic:
                    budget_violations += [{'case_id':case['id'],'turn':index,'error':error}
                                          for error in budget_contract_errors(answer,bundle['protocol']['budgets']['unicode_chars'])]
                record = {'turn': index, 'public_message': turn['message'], 'answer': answer,
                          'state_before': before, 'state_after': after, 'metrics': stage_metrics(answer),
                          'wall_seconds': time.perf_counter() - start, 'execution': 'synthetic_fixture' if synthetic else 'live_online'}
            except (ValueError, KeyError, TypeError, OSError) as exc:
                row['status'] = 'BLOCKED_INPUT' if str(exc) == 'MISSING_VISUAL_INPUT' else 'EXECUTION_ERROR'
                record = {'turn': index, 'public_message': turn['message'], 'status': row['status'],
                          'error': str(exc), 'error_type': type(exc).__name__, 'wall_seconds': time.perf_counter() - start}
                row['turns'].append(record)
                break
            row['turns'].append(record)
        rows.append(row)
        exclusive_write(out / (case['id'] + '.json'), row)
    code_after = _code_fingerprint()
    code_changed = code_before != code_after
    model_identity_after = _runtime_model_identity(agent, synthetic)
    model_identity_changed = model_identity != model_identity_after
    run = {'schema': SCHEMA, 'status': 'CODE_CHANGED' if code_changed else 'MODEL_CONFIG_CHANGED' if model_identity_changed else 'BUDGET_CONTRACT_VIOLATION' if budget_violations else 'PARTIAL' if any(r['status'] != 'EXECUTED' for r in rows) else 'EXECUTED',
           'run_id': str(uuid.uuid4()), 'mode': mode, 'execution_origin': 'synthetic_fixture' if synthetic else 'live_online',
           'method': method, 'comparison_family': comparison_family,
           'comparison_policy': bundle['protocol']['comparison_families'][comparison_family],
           'snapshot_id': snapshot_id, 'hashes': bundle['hashes'], 'budgets': bundle['protocol']['budgets'],
           'model_policy': bundle['protocol'].get('model_policy'), 'case_ids': sorted(selected),
           'runtime_model_identity': model_identity, 'code_hash': digest(code_before),
           'actual_budget_definition':BUDGET_DEFINITION,'actual_budget_definition_hash':BUDGET_DEFINITION_HASH,
           'budget_contract_violations':budget_violations,
           'runtime_model_identity_after': model_identity_after, 'model_identity_changed': model_identity_changed,
           'code_hash_after': digest(code_after), 'code_changed': code_changed,
           'freeze_id': frozen['freeze_id'] if frozen else None, 'frozen_path': str(frozen_path) if frozen_path else None,
           'created_at': now(), 'rows': rows, 'formal_success_rate': None,
           'limitations': ['Expected goals never supplied to Agent.', 'Exploratory and fixture runs are not formal scores.',
                           'Usage unavailable in ordinary Agent answers remains unknown.', 'Product workflow capability differences are kept explicit.']}
    run['run_hash'] = digest(run)
    exclusive_write(out / 'run.json', run)
    return run


def _subset(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and _subset(actual[k], v) for k, v in expected.items())
    if isinstance(expected, bool):
        return isinstance(actual, bool) and actual is expected
    return actual == expected


def _automatic_goal(goal, turn, method=None):
    answer = turn.get('answer', {})
    if not answer or answer.get('status') in BAD_TERMINAL:
        return False, 'NO_VALID_CURRENT_ANSWER'
    kind = goal['kind']
    if method == 'product':
        # A lexical RAG can correctly clarify or preserve conversational inputs
        # without implementing the Agent's task-state/status/receipt schema.
        return None, 'PRODUCT_ANSWER_REQUIRES_INDEPENDENT_CONTENT_AND_SUPPORT_REVIEW'
    if kind == 'status':
        return answer.get('status') in goal.get('allowed_statuses', []), 'TERMINAL_STATUS_CHECK'
    if kind == 'state':
        return _subset(turn.get('state_after', {}).get('inputs', {}), goal['expected_inputs']), 'STATE_FIELDS_CHECK'
    if kind == 'knowledge':
        return None, 'INDEPENDENT_ANSWER_REVIEW_REQUIRED'
    refs = answer.get('calculation_trace_refs', [])
    traces = [c for c in answer.get('calculation_traces', [])
              if c.get('rule_id') == goal['rule_id'] and c.get('run_id') in refs
              and c.get('task_revision') == answer.get('task_revision') and c.get('snapshot_id') == answer.get('snapshot_id')
              and _subset(c.get('user_inputs', {}), goal.get('expected_params', {}))]
    return any(_subset(c.get('outputs', {}), goal.get('expected_outputs', {})) for c in traces), 'INDEPENDENT_REFERENCE_VS_CURRENT_CITED_TOOL_OUTPUT'


def score_run(bundle, run, *, judgments=None):
    if run.get('hashes') != bundle['hashes'] or run.get('run_hash') != digest({k: v for k, v in run.items() if k != 'run_hash'}):
        raise ValidationError('EVALUATION_RUN_CHANGED')
    if run.get('mode') == 'formal':
        if run.get('code_changed'):
            raise ValidationError('CODE_CHANGED_DURING_FORMAL_RUN')
        if run.get('model_identity_changed'):
            raise ValidationError('MODEL_CONFIG_CHANGED_DURING_FORMAL_RUN')
        if run.get('budget_contract_violations'):
            raise ValidationError('BUDGET_CONTRACT_VIOLATION')
        frozen = verify_frozen(bundle, run['frozen_path'])
        if frozen['freeze_id'] != run.get('freeze_id') or run.get('execution_origin') != 'live_online':
            raise ValidationError('FORMAL_RUN_NOT_VERIFIED')
    judgments = judgments or {'reviews': []}
    if judgments.get('reviews') and (judgments.get('run_hash') != run['run_hash'] or judgments.get('review_kind') != 'answer_outcomes'):
        raise ValidationError('ANSWER_REVIEW_RUN_MISMATCH')
    keys = [(r.get('case_id'), r.get('goal_id')) for r in judgments.get('reviews', [])]
    if len(set(keys)) != len(keys):
        raise ValidationError('DUPLICATE_ANSWER_REVIEWS')
    reviewed = {key: row for key, row in zip(keys, judgments.get('reviews', []))}
    expected = {c['id']: c for c in bundle['cases']}
    row_ids = [r.get('case_id') for r in run.get('rows', [])]
    if len(row_ids) != len(set(row_ids)) or set(row_ids) != set(run.get('case_ids', [])) or not set(row_ids) <= set(expected):
        raise ValidationError('RUN_CASE_SET_MISMATCH')
    rows = []
    for row in run['rows']:
        case = expected[row['case_id']]
        if row['case_hash'] != case_hash(case):
            raise ValidationError('EXPECTED_CASE_CHANGED')
        turns = {t['turn']: t for t in row['turns']}
        if len(turns) != len(row['turns']):
            raise ValidationError('DUPLICATE_RUN_TURN')
        goals = []
        for goal in case['expected_goals']:
            turn = turns.get(goal['turn'], {})
            blocked_input = row.get('status') == 'BLOCKED_INPUT' and not turn.get('answer')
            passed, basis = (None, 'INPUT_NOT_AVAILABLE') if blocked_input else _automatic_goal(goal, turn, run['method'])
            review = reviewed.get((case['id'], goal['id']), {})
            human_valid = (_approved_review(review) and review.get('case_hash') == case_hash(case)
                           and type(review.get('passed')) is bool)
            requires_human = goal.get('requires_answer_review', True)
            outcome = 'BLOCKED_INPUT' if blocked_input else 'FAIL' if passed is False or (human_valid and not review['passed']) else \
                      'PENDING_HUMAN' if (passed is None or requires_human) and not human_valid else 'PASS'
            initial = turn.get('metrics', {}).get('initial_retrieval', {}).get('selected_ids', [])
            groups = goal.get('required_evidence_groups', [])
            coverage = sum(bool(set(g['alternatives']) & set(initial)) for g in groups) / len(groups) if groups else None
            goals.append({'goal_id': goal['id'], 'turn': goal['turn'], 'automatic_check': passed, 'basis': basis,
                          'human_reviewed': human_valid, 'outcome': outcome, 'initial_evidence_group_coverage': coverage})
        outcome = 'BLOCKED_INPUT' if any(g['outcome'] == 'BLOCKED_INPUT' for g in goals) else 'FAIL' if any(g['outcome'] == 'FAIL' for g in goals) else 'PASS' if all(g['outcome'] == 'PASS' for g in goals) else 'PENDING_HUMAN'
        rows.append({'case_id': case['id'], 'outcome': outcome, 'goals': goals,
                     'stage_metrics': [t.get('metrics', {}) for t in row['turns']],
                     'wall_seconds': sum(t.get('wall_seconds', 0) for t in row['turns'])})
    counts = dict(Counter(r['outcome'] for r in rows))
    eligible = (run['mode'] == 'formal' and run['execution_origin'] == 'live_online'
                and not counts.get('PENDING_HUMAN') and not counts.get('BLOCKED_INPUT') and len(rows) == len(run['case_ids']))
    summary = {'schema': SCHEMA, 'status': 'FORMAL_SCORED' if eligible else 'EXPLORATORY_OR_PENDING_REVIEW',
               'run_hash': run['run_hash'], 'hashes': run['hashes'], 'snapshot_id': run['snapshot_id'],
               'method': run['method'], 'comparison_family': run['comparison_family'], 'budgets': run['budgets'],
               'comparison_policy': run['comparison_policy'],
               'model_policy': run['model_policy'], 'case_ids': run['case_ids'], 'mode': run['mode'],
               'runtime_model_identity': run['runtime_model_identity'], 'code_hash': run['code_hash'], 'code_changed': run['code_changed'],
               'model_identity_changed': run.get('model_identity_changed', False),
               'actual_budget_definition_hash':run['actual_budget_definition_hash'],
               'budget_contract_violations':run['budget_contract_violations'],
               'execution_origin': run['execution_origin'], 'counts': counts, 'rows': rows,
               'evaluated_cases': len(rows), 'dataset_cases': len(bundle['cases']), 'full_dataset_run': len(rows) == len(bundle['cases']),
               'formal_success_rate': counts.get('PASS', 0) / len(rows) if eligible and rows else None,
               'note': 'Automatic numeric/state checks and human answer support are separate; runtime TaskSpec is not gold.'}
    return summary


def compare_runs(scores):
    if len(scores) < 2:
        raise ValidationError('COMPARISON_REQUIRES_TWO_RUNS')
    if any(s.get('code_changed') for s in scores):
        raise ValidationError('CODE_CHANGED_DURING_RUN')
    if any(s.get('model_identity_changed') for s in scores):
        raise ValidationError('MODEL_CONFIG_CHANGED_DURING_RUN')
    if any(s.get('budget_contract_violations') for s in scores):raise ValidationError('BUDGET_CONTRACT_VIOLATION')
    if any(not s.get('actual_budget_definition_hash') for s in scores):raise ValidationError('MISSING_ACTUAL_BUDGET_DEFINITION')
    if any(not s.get('code_hash') or s.get('runtime_model_identity', {}).get('kind') not in ('configured_live_client', 'synthetic_fixture') for s in scores):
        raise ValidationError('RUNTIME_MODEL_IDENTITY_UNAVAILABLE')
    shared = ('hashes', 'snapshot_id', 'budgets', 'model_policy', 'runtime_model_identity', 'code_hash',
              'case_ids', 'mode', 'execution_origin', 'comparison_family', 'comparison_policy','actual_budget_definition_hash')
    for key in shared:
        if any(s.get(key) != scores[0].get(key) for s in scores[1:]):
            raise ValidationError('UNFAIR_COMPARISON:' + key)
    if len({s['method'] for s in scores}) != len(scores):
        raise ValidationError('DUPLICATE_COMPARISON_METHOD')
    methods = [s['method'] for s in scores]
    by_method = {s['method']: {r['case_id']: r for r in s['rows']} for s in scores}
    pairs = []
    for case_id in scores[0]['case_ids']:
        outcomes = {m: by_method[m].get(case_id, {}).get('outcome', 'NOT_RUN') for m in methods}
        determined = all(x in ('PASS', 'FAIL') for x in outcomes.values())
        pairs.append({'case_id': case_id, 'outcomes': outcomes,
                      'winners': [m for m in methods if outcomes[m] == 'PASS'] if determined and len(set(outcomes.values())) > 1 else [],
                      'comparison': 'TIE' if determined and len(set(outcomes.values())) == 1 else 'DIFFERENCE' if determined else 'UNSCORED',
                      'wall_seconds': {m: by_method[m].get(case_id, {}).get('wall_seconds') for m in methods}})
    return {'status': 'COMPARED', 'methods': methods, 'fairness_fields': shared, 'pairs': pairs,
            'comparison_family': scores[0]['comparison_family'], 'comparison_policy': scores[0]['comparison_policy'],
            'formal': all(s['status'] == 'FORMAL_SCORED' for s in scores),
            'note': 'Unreviewed cases remain UNSCORED; no ranking is inferred from missing results or model self-checks.'}
