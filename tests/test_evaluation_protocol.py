"""Synthetic protocol tests, never counted as independent product evaluation."""
import copy
import json
from pathlib import Path

import pytest
from types import SimpleNamespace

from stardew_agent.core import ROOT, ValidationError, digest, file_hash, write
from stardew_agent.evaluation_protocol import (
    SCHEMA, load_protocol, validate_protocol, export_review, freeze_protocol,
    run_cases, score_run, compare_runs, stage_metrics, exclusive_write, case_hash,
)


@pytest.fixture
def protocol(tmp_path):
    p = json.loads((ROOT / 'evaluation/protocols/post_midterm.json').read_text())
    cases = json.loads((ROOT / p['cases_path']).read_text())
    sources = json.loads((ROOT / p['sources_path']).read_text())
    cases = [c for c in cases if c['id'] in ('PM-02', 'PM-04', 'PM-05', 'PM-09')]
    p.update(cases_path='cases.json', sources_path='sources.json')
    write(tmp_path / 'protocol.json', p)
    write(tmp_path / 'cases.json', cases)
    write(tmp_path / 'sources.json', sources)
    return load_protocol(tmp_path / 'protocol.json', root=tmp_path)


class FakeAgent:
    """Answers chosen from public messages; expected_goals are never passed in."""
    def __init__(self, tasks, seen, method):
        self.tasks, self.seen, self.method = tasks, seen, method

    def run(self, task_id, message):
        self.seen.append((task_id, message))
        task = self.tasks.get(task_id)
        quantity = 8 if '改成8个' in message else 12 if '12个' in message else 3
        task = self.tasks.update(task_id, task['revision'], {'quantity': quantity})
        # Explicit synthetic fixture values, not the production calculator.
        amount = {3: 330, 8: 880, 12: 1320}[quantity]
        calc = {'rule_id': 'sale_value', 'run_id': 'synthetic:' + str(task['revision']),
                'task_revision': task['revision'], 'snapshot_id': task['snapshot_id'],
                'user_inputs': {'entity_id': 'entity:Kale', 'quantity': quantity, 'quality': 'normal', 'profession': 'none'},
                'outputs': {'sales_g': amount}}
        return {'status': 'CANDIDATE_ANSWER', 'answer_text': f'合计 {amount}g',
                'task_revision': task['revision'], 'snapshot_id': task['snapshot_id'],
                'calculation_trace_refs': [calc['run_id']], 'calculation_traces': [calc],
                'tool_events': [{'tool': 'retrieve_knowledge', 'model_call_number': 1, 'elapsed_seconds': .1,
                                 'result': {'trace': {'selected_ids': ['fact:fixture'], 'method': self.method,
                                                       'budget_used': {'final_records': 1}}}},
                                {'tool': 'execute_rule', 'model_call_number': 2, 'elapsed_seconds': .05, 'result': calc}],
                'elapsed_seconds': .2}


def fixture_factory(seen):
    def factory(*, tasks, method, run_dir, budgets):
        assert set(budgets) == {'pages', 'candidate_entities', 'edge_reads', 'hops', 'final_records', 'images', 'unicode_chars'}
        return FakeAgent(tasks, seen, method)
    return factory


def synthetic_run(protocol, tmp_path, cases=('PM-02',), method='D'):
    return run_cases(protocol, tmp_path / method, case_ids=cases, method=method,
                     agent_factory=fixture_factory([]))


def rehash(run):
    run['run_hash'] = digest({k: v for k, v in run.items() if k != 'run_hash'})


def test_missing_visual_inputs_are_visible_blockers(protocol):
    r = validate_protocol(protocol)
    assert not r['errors']
    assert 'PM-09:TURN_0_IMAGE_PENDING' in r['formal_blockers']
    assert not r['formal_ready']


def test_complete_multiturn_export_and_blank_human_decisions(protocol, tmp_path):
    result = export_review(protocol, tmp_path / 'review')
    md = (tmp_path / 'review/完整逐轮待审目录.md').read_text()
    assert '12个普通甘蓝' in md and '数量改成8个' in md and '用户第 2 轮' in md
    review = json.loads((tmp_path / 'review/gold_review_template.json').read_text())
    assert all(x['actor_kind'] is None and x['decision'] is None for x in review['reviews'])
    assert result['gold_reviewed'] == 0


def test_run_public_turns_share_task_without_expected_goals(protocol, tmp_path):
    seen = []
    run = run_cases(protocol, tmp_path / 'run', case_ids=['PM-05'], agent_factory=fixture_factory(seen))
    assert len(seen) == 2 and seen[0][0] == seen[1][0]
    assert [x[1] for x in seen] == ['12个普通甘蓝，无职业，直接卖多少钱？', '数量改成8个，其他条件不变。']
    assert run['execution_origin'] == 'synthetic_fixture'
    assert run['rows'][0]['turns'][1]['state_after']['inputs']['quantity'] == 8
    scores = score_run(protocol, run)
    assert all(g['automatic_check'] for g in scores['rows'][0]['goals'])
    assert scores['formal_success_rate'] is None


def test_numeric_trace_does_not_satisfy_knowledge_subgoal(protocol, tmp_path):
    run = synthetic_run(protocol, tmp_path, ('PM-04',))
    score = score_run(protocol, run)
    checks = {g['goal_id']: g for g in score['rows'][0]['goals']}
    assert checks['sale']['automatic_check'] is True
    assert checks['explanation']['outcome'] == 'PENDING_HUMAN'
    assert score['rows'][0]['outcome'] != 'PASS'


def test_stale_calculation_cannot_pass_goal(protocol, tmp_path):
    run = synthetic_run(protocol, tmp_path)
    run['rows'][0]['turns'][0]['answer']['calculation_traces'][0]['task_revision'] = -1
    rehash(run)
    score = score_run(protocol, run)
    assert score['rows'][0]['outcome'] == 'FAIL'


def test_missing_image_is_blocked_not_zero_cost_success(protocol, tmp_path):
    seen = []
    run = run_cases(protocol, tmp_path / 'missing', case_ids=['PM-09'], agent_factory=fixture_factory(seen))
    assert not seen and run['rows'][0]['status'] == 'BLOCKED_INPUT'
    assert score_run(protocol, run)['rows'][0]['outcome'] == 'BLOCKED_INPUT'


def test_no_online_call_without_opt_in(protocol, tmp_path):
    with pytest.raises(ValidationError, match='EXPLICIT_ONLINE'):
        run_cases(protocol, tmp_path / 'not-online', case_ids=['PM-02'])


def test_fake_agent_cannot_claim_formal(protocol, tmp_path):
    with pytest.raises(ValidationError, match='SYNTHETIC_AGENT'):
        run_cases(protocol, tmp_path / 'fake-formal', mode='formal', agent_factory=fixture_factory([]))


def test_candidate_run_cannot_freeze_unreviewed(protocol, tmp_path):
    protocol['cases'] = [c for c in protocol['cases'] if c['id'] == 'PM-02']
    export_review(protocol, tmp_path / 'review')
    with pytest.raises(ValidationError, match='INDEPENDENT_GOLD_REVIEW_PENDING'):
        freeze_protocol(protocol, tmp_path / 'review/gold_review_template.json', tmp_path / 'not-read.json', tmp_path / 'freeze.json')


def test_model_review_not_human_approval(protocol, tmp_path):
    protocol['cases'] = [c for c in protocol['cases'] if c['id'] == 'PM-02']
    export_review(protocol, tmp_path / 'review')
    p = tmp_path / 'review/gold_review_template.json'
    reviews = json.loads(p.read_text())
    reviews['reviews'][0].update(decision='approve', actor_kind='model', actor_id='ChatECNU',
                                 reason='supported', reviewed_at='2026-11-17T00:00:00Z', review_origin='explicit_human_review')
    write(p, reviews)
    with pytest.raises(ValidationError, match='INDEPENDENT_GOLD_REVIEW_PENDING'):
        freeze_protocol(protocol, p, tmp_path / 'not-read.json', tmp_path / 'freeze.json')


def test_review_hash_binds_exact_dataset(protocol, tmp_path):
    protocol['cases'] = [c for c in protocol['cases'] if c['id'] == 'PM-02']
    export_review(protocol, tmp_path / 'review')
    p = tmp_path / 'review/gold_review_template.json'
    reviews = json.loads(p.read_text());reviews['dataset_hash'] = 'other'
    write(p, reviews)
    with pytest.raises(ValidationError, match='GOLD_REVIEW_HASH_MISMATCH'):
        freeze_protocol(protocol, p, tmp_path / 'none.json', tmp_path / 'freeze.json')


def test_capture_family_cross_split_rejected_but_common_sprite_allowed(protocol, tmp_path):
    p = tmp_path / 'image.bin';p.write_bytes(b'independent fixture image bytes')
    base = {'path': str(p), 'sha256': file_hash(p), 'entity_id': 'entity:Kale', 'review_status': 'pending'}
    protocol['sources'] += [{**base, 'id': 'template', 'kind': 'wiki_template', 'split': 'gallery'},
                            {**base, 'id': 'query', 'kind': 'real_screenshot', 'capture_group': 'session-1', 'split': 'test'}]
    assert not validate_protocol(protocol)['errors']
    protocol['sources'].append({**base, 'id': 'query-crop', 'kind': 'real_screenshot', 'capture_group': 'session-1', 'split': 'development'})
    assert 'CAPTURE_GROUP_SPLIT_LEAKAGE' in validate_protocol(protocol)['errors']


def test_identity_label_leak_is_not_silently_accepted(protocol):
    case = protocol['cases'][0]
    case.update(identity_visibility='hidden', hidden_identity_labels=['甘蓝'])
    assert any('IDENTITY_LABEL_IN_QUERY' in e for e in validate_protocol(protocol)['errors'])


def test_synthetic_image_not_reported_real(protocol, tmp_path):
    p = tmp_path / 'image.bin';p.write_bytes(b'fixture')
    protocol['sources'].append({'id': 'image', 'path': str(p), 'sha256': file_hash(p), 'kind': 'synthetic_image',
                                'capture_group': 'synthetic-1', 'split': 'development', 'claim_scope': 'independent_real_screenshot'})
    assert 'SYNTHETIC_REAL_CLAIM:image' in validate_protocol(protocol)['errors']


def test_first_retrieval_and_supplementation_costs_not_conflated():
    answer = {'tool_events': [
        {'tool': 'retrieve_knowledge', 'model_call_number': 1, 'result': {'trace': {'selected_ids': ['first'], 'budget_used': {'final_records': 1}}}},
        {'tool': 'fetch_dependencies', 'model_call_number': 2, 'result': {'trace': {'records_examined': 20, 'total_seconds': .5}}},
        {'tool': 'retrieve_knowledge', 'model_call_number': 2, 'result': {'trace': {'selected_ids': ['later']}}}]}
    result = stage_metrics(answer)
    assert result['initial_retrieval']['selected_ids'] == ['first']
    assert result['supplementation']['rounds'] == 1 and result['supplementation']['records_examined'] == 20
    assert result['cost']['model_calls_lower_bound'] == 2 and result['cost']['tokens'] is None


def test_different_budgets_cannot_be_compared(protocol, tmp_path):
    a = score_run(protocol, synthetic_run(protocol, tmp_path, method='BQ'))
    b = score_run(protocol, synthetic_run(protocol, tmp_path, method='D'))
    pairs = compare_runs([a, b]);assert not pairs['formal']
    assert pairs['pairs'][0]['comparison'] == 'UNSCORED'
    b['budgets'] = {**b['budgets'], 'images': 99}
    with pytest.raises(ValidationError, match='UNFAIR_COMPARISON:budgets'):
        compare_runs([a, b])


def test_run_mutation_and_omitted_cases_rejected(protocol, tmp_path):
    run = synthetic_run(protocol, tmp_path)
    run['rows'][0]['case_id'] = 'PM-05'
    with pytest.raises(ValidationError, match='EVALUATION_RUN_CHANGED'):
        score_run(protocol, run)
    rehash(run)
    with pytest.raises(ValidationError, match='RUN_CASE_SET_MISMATCH'):
        score_run(protocol, run)


def test_output_is_immutable(tmp_path):
    exclusive_write(tmp_path / 'frozen.json', {'one': 1})
    with pytest.raises(ValidationError, match='ALREADY_EXISTS'):
        exclusive_write(tmp_path / 'frozen.json', {'one': 2})


def test_product_no_calculator_trace_is_pending_not_automatic_failure(protocol, tmp_path):
    run = synthetic_run(protocol, tmp_path, method='product')
    run['rows'][0]['turns'][0]['answer']['calculation_traces'] = []
    rehash(run)
    goal = score_run(protocol, run)['rows'][0]['goals'][0]
    assert goal['automatic_check'] is None and goal['outcome'] == 'PENDING_HUMAN'


def test_answer_review_bound_to_exact_run(protocol, tmp_path):
    run = synthetic_run(protocol, tmp_path)
    with pytest.raises(ValidationError, match='ANSWER_REVIEW_RUN_MISMATCH'):
        score_run(protocol, run, judgments={'review_kind': 'answer_outcomes', 'run_hash': 'wrong', 'reviews': [{'case_id': 'PM-02'}]})


def test_unsafe_case_id_and_runtime_self_gold_rejected(protocol):
    protocol['cases'][0]['id'] = '../../escape'
    protocol['cases'][0]['expected_origin'] = 'runtime_taskspec'
    errs = validate_protocol(protocol)['errors']
    assert 'UNSAFE_CASE_ID' in errs
    assert any('SELF_DERIVED_EXPECTATION' in x for x in errs)


def test_runtime_identity_contains_only_public_model_fields():
    from stardew_agent.evaluation_protocol import _runtime_model_identity
    config = {'CHATECNU_BASE_URL': 'https://fixture-user:fixture-pass@example.test/api?token=fixture-secret',
              'CHATECNU_MODEL': 'fixture-text', 'CHATECNU_VISION_MODEL': 'fixture-vision',
              'CHATECNU_API_KEY': 'fixture-key-never-serialize'}
    agent = SimpleNamespace(client=SimpleNamespace(client=SimpleNamespace(config=config)))
    identity = _runtime_model_identity(agent, False)
    assert identity == {'kind': 'configured_live_client', 'base_url': 'https://example.test/api',
                        'text_model': 'fixture-text', 'vision_model': 'fixture-vision'}
    assert 'fixture-key' not in json.dumps(identity) and 'fixture-pass' not in json.dumps(identity)


def test_code_changed_during_run_cannot_compare(protocol, tmp_path, monkeypatch):
    from stardew_agent import evaluation_protocol as ep
    fingerprints = iter([{'code.py': 'before'}, {'code.py': 'after'}])
    monkeypatch.setattr(ep, '_code_fingerprint', lambda: next(fingerprints))
    run = synthetic_run(protocol, tmp_path)
    assert run['status'] == 'CODE_CHANGED' and run['code_changed']
    score = score_run(protocol, run)
    with pytest.raises(ValidationError, match='CODE_CHANGED_DURING_RUN'):
        compare_runs([score, copy.deepcopy(score)])


@pytest.mark.parametrize('field,value', [('code_hash', 'different-code'),
    ('actual_budget_definition_hash','different-budget-definition'),
    ('runtime_model_identity', {'kind': 'configured_live_client', 'text_model': 'different'})])
def test_actual_code_and_model_identity_required_for_fairness(protocol, tmp_path, field, value):
    a = score_run(protocol, synthetic_run(protocol, tmp_path, method='B'))
    b = copy.deepcopy(a);b['method'] = 'D';b[field] = value
    with pytest.raises(ValidationError, match='UNFAIR_COMPARISON:' + field):
        compare_runs([a, b])


def test_model_config_change_kept_and_rejected(protocol, tmp_path, monkeypatch):
    from stardew_agent import evaluation_protocol as ep
    identities = iter([{'kind': 'configured_live_client', 'text_model': 'before'},
                       {'kind': 'configured_live_client', 'text_model': 'after'}])
    monkeypatch.setattr(ep, '_runtime_model_identity', lambda *args: next(identities))
    run = synthetic_run(protocol, tmp_path)
    assert run['status'] == 'MODEL_CONFIG_CHANGED' and run['model_identity_changed']
    score = score_run(protocol, run)
    with pytest.raises(ValidationError, match='MODEL_CONFIG_CHANGED_DURING_RUN'):
        compare_runs([score, copy.deepcopy(score)])


def test_product_clarification_uses_answer_review_not_agent_status():
    from stardew_agent.evaluation_protocol import _automatic_goal
    goal = {'kind': 'status', 'allowed_statuses': ['NEEDS_INPUT']}
    turn = {'answer': {'status': 'BASELINE_CANDIDATE_ANSWER', 'answer_text': '请提供数量和品质。'}}
    passed, basis = _automatic_goal(goal, turn, 'product')
    assert passed is None and basis.startswith('PRODUCT_ANSWER_REQUIRES_INDEPENDENT')


def test_visual_v2_preserves_questions_gold_and_original_missing_inputs():
    original = load_protocol(ROOT / 'evaluation/protocols/post_midterm.json')
    revised = load_protocol(ROOT / 'evaluation/datasets/post_midterm/visual_ready_v2/protocol.json')
    for a, b in zip(original['cases'], revised['cases']):
        assert a['expected_goals'] == b['expected_goals']
        assert [t['message'] for t in a['turns']] == [t['message'] for t in b['turns']]
    assert validate_protocol(original)['candidate_inputs_ready'] is False
    validation = validate_protocol(revised)
    assert validation['candidate_inputs_ready'] is True and validation['formal_ready'] is False
    images = [s for s in revised['sources'] if s['kind'] == 'real_screenshot']
    assert len(images) == 44
    assert {s['split'] for s in images} == {'development'}
    assert {s['claim_scope'] for s in images} == {'diagnostic_reused_capture'}
    assert all(s['review_status'] == 'PENDING_HUMAN' for s in images)


def test_visual_query_bytes_enter_task_but_draft_labels_do_not(tmp_path, monkeypatch):
    from stardew_agent import online_vision
    revised = load_protocol(ROOT / 'evaluation/datasets/post_midterm/visual_ready_v2/protocol.json')
    received = []
    class FakeStore:
        def upload(self, data, task_id):
            received.append(data)
            return {'image_id': 'neutral-upload', 'task_id': task_id}
        def region(self, image_id, task_id, bbox):
            return {'region_id': 'neutral-region', 'image_id': image_id, 'task_id': task_id, 'bbox': bbox,
                    'path': 'neutral-query.png', 'sha256': digest(received[-1])}
    class VisualAgent:
        def __init__(self, tasks):self.tasks = tasks
        def run(self, task_id, message):
            task = self.tasks.get(task_id)
            assert task['selected_regions'][0]['region_id'] == 'neutral-region'
            assert not any(label in json.dumps(task) for label in ('Melon', 'Parsnip', 'draft_labels', 'expected_goals'))
            return {'status': 'CANDIDATE_ANSWER', 'answer_text': 'fixture visual response'}
    monkeypatch.setattr(online_vision, 'ImageStore', FakeStore)
    run = run_cases(revised, tmp_path / 'visual', case_ids=['PM-09', 'PM-10'],
                    agent_factory=lambda *, tasks, **kw: VisualAgent(tasks))
    assert all(row['status'] == 'EXECUTED' for row in run['rows']) and len(received) == 2
    assert received[0] == (ROOT / 'verification/data/visual_crops/V01.png').read_bytes()
    assert received[1] == (ROOT / 'verification/data/visual_crops/V10.png').read_bytes()
    assert score_run(revised, run)['formal_success_rate'] is None


def test_visual_input_readiness_does_not_approve_gold(tmp_path):
    directory = ROOT / 'evaluation/datasets/post_midterm/visual_ready_v2'
    revised = load_protocol(directory / 'protocol.json')
    with pytest.raises(ValidationError, match='INDEPENDENT_GOLD_REVIEW_PENDING'):
        freeze_protocol(revised, directory / 'review/gold_review_template.json', tmp_path / 'not-used.json', tmp_path / 'freeze.json')


@pytest.mark.parametrize('status',['REPEATED_FAILURE_STOP','STATE_CHANGED','CANCELLED','MODEL_ERROR','BLOCKED'])
def test_terminal_failures_do_not_become_pending_knowledge_review(status):
    from stardew_agent.evaluation_protocol import _automatic_goal
    passed,basis=_automatic_goal({'kind':'knowledge'},{'answer':{'status':status,'answer_text':'Stopped.'}},'D')
    assert passed is False and basis=='NO_VALID_CURRENT_ANSWER'
