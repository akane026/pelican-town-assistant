"""Fixture-only boundary tests; these do not measure product accuracy."""
import json
from types import SimpleNamespace

import pytest

from stardew_agent import product_baseline as pb, parsing
from stardew_agent.core import ValidationError, file_hash, write
from stardew_agent.state import TaskStore


class SourceOnly(dict):
    def __getitem__(self, key):
        assert key in ('evidence', 'occurrences'), 'Baseline accessed structured graph facts or relations'
        return super().__getitem__(key)


class FakeClient:
    def __init__(self, *, vision_failure=False, final_response=None, after_call=None):
        self.calls = []
        self.images = []
        self.vision_failure = vision_failure
        self.final_response = final_response
        self.after_call = after_call

    def image(self, path):
        self.images.append(path)
        return {'type': 'image_url', 'image_url': {'url': 'fixture://image'}}

    def call(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        if kwargs['vision']:
            result = {'status': 'ERROR', 'reason': 'FIXTURE_VISION_FAILURE'} if self.vision_failure else {'status': 'OK', 'content': 'ambiguous fixture pixels'}
        elif self.final_response is not None:
            result = self.final_response
        else:
            packet = json.loads(messages[-1]['content'].split('\nUNVERIFIED_VISUAL_OBSERVATION:')[0].split('\nVISUAL_OBSERVATION_UNAVAILABLE')[0])
            result = {'status': 'OK', 'content': json.dumps({'answer_text': 'Fixture answer, unreviewed.',
                'claim_evidence_refs': [packet['evidence']['source_chunks'][0]['id']], 'missing_inputs': []})}
        if self.after_call:
            self.after_call(len(self.calls))
        return result


@pytest.fixture
def baseline(tmp_path, monkeypatch):
    monkeypatch.setattr(pb, 'ROOT', tmp_path)
    monkeypatch.setattr(parsing, 'ROOT', tmp_path)
    write(tmp_path / 'configs/aliases.json', {'Kale': ['甘蓝']})
    source = tmp_path / 'wiki.html'
    source.write_text('<html><h2>Fixture source</h2><p>Kale is a fixture crop. Raw source prose.</p>'
                      '<table><tr><th>Raw field</th><td>110</td></tr></table></html>')
    evidence = {'source_id': 'source:fixture', 'page_id': 'Kale', 'raw_path': 'wiki.html',
                'source_sha256': file_hash(source), 'revision_id': 'fixture-revision', 'url': 'https://example.test/Kale'}
    snapshot = SimpleNamespace(id='task-bound-fixture-snapshot', domain=SourceOnly(evidence=[evidence], occurrences=[]), records={'assets': {}})
    snapshots = []
    def get_snapshot(snapshot_id, allow_candidate=False):
        assert snapshot_id == snapshot.id and allow_candidate
        snapshots.append(snapshot_id)
        return snapshot
    monkeypatch.setattr(pb, 'Snapshot', get_snapshot)
    monkeypatch.setattr(pb, 'ModelClient', lambda: pytest.fail('Real model initialization is forbidden in fixture tests'))
    tasks = TaskStore(tmp_path / 'tasks.sqlite3')
    task = tasks.create(snapshot.id)
    return SimpleNamespace(root=tmp_path, tasks=tasks, task=task, snapshot=snapshot, snapshots=snapshots)


def image_region(baseline, *, role='query'):
    path = baseline.root / (role + '.png')
    path.write_bytes(b'fixture image bytes ' + role.encode())
    if role == 'query':
        region = {'region_id': 'region:fixture', 'task_id': baseline.task['task_id'], 'path': path.name, 'sha256': file_hash(path)}
        baseline.tasks.save_runtime(baseline.task['task_id'], baseline.tasks.get(baseline.task['task_id'])['revision'], selected_regions=[region])
        return region
    baseline.snapshot.records['assets']['asset:' + role] = {'id': 'asset:' + role, 'path': path.name, 'sha256': file_hash(path)}
    baseline.snapshot.domain['occurrences'].append({'page_id': 'Kale', 'asset_id': 'asset:' + role, 'locator': 'image:' + role})
    return path


def test_reads_original_text_and_tables_without_graph_values(baseline):
    client = FakeClient()
    product = pb.ProductRAG(baseline.tasks, client=client)
    result = product.run(baseline.task['task_id'], '甘蓝是什么？')
    assert result['status'] == 'BASELINE_CANDIDATE_ANSWER'
    chunks = result['baseline']['source_chunks']
    assert any(c['text'] == 'Raw field | 110' for c in chunks)
    assert all(c['id'].startswith('source_chunk:') for c in chunks)
    assert result['snapshot_id'] == baseline.snapshot.id
    assert not result['baseline']['graph_traversal'] and not result['calculation_traces']
    assert result['completion_scope'] == 'unverified_baseline_answer'
    assert result['independently_verified'] is False
    assert not client.calls[0][1]['vision']
    assert 'expected_goals' not in json.dumps(client.calls)


def test_all_multiturn_text_preserved_without_old_evidence_bundles(baseline):
    for i in range(14):
        baseline.tasks.message(baseline.task['task_id'], 'user', f'prior raw user turn {i}')
        baseline.tasks.message(baseline.task['task_id'], 'assistant', {'answer_text': f'prior answer {i}',
            'baseline': {'source_chunks': ['FORBIDDEN_OLD_EVIDENCE']}, 'goal_spec': 'FORBIDDEN_TASKSPEC'})
    client = FakeClient()
    result = pb.ProductRAG(baseline.tasks, client=client).run(baseline.task['task_id'], '请继续')
    packet = json.loads(client.calls[-1][0][-1]['content'])
    assert len(packet['history']) == 28 and packet['history'][0]['content'] == 'prior raw user turn 0'
    assert packet['history'][-1]['content'] == 'prior answer 13'
    assert 'FORBIDDEN_' not in json.dumps(packet)
    assert result['baseline']['history_messages'] == 28
    assert result['task_revision'] == 1


def test_vision_observation_then_same_text_role_with_shared_image_budget(baseline):
    image_region(baseline)
    for name in ('one', 'two', 'three', 'four'):
        image_region(baseline, role=name)
    client = FakeClient()
    result = pb.ProductRAG(baseline.tasks, client=client, budgets={'images': 2, 'unicode_chars': 6000}).run(baseline.task['task_id'], '图里是什么？')
    assert [c[1]['vision'] for c in client.calls] == [True, False]
    assert all(c[1]['temperature'] == 0 for c in client.calls)
    assert len(client.images) == 2 and client.images[0].name == 'query.png'
    assert result['baseline']['images'][0]['role'] == 'user_roi'
    assert result['baseline']['model_requests'] == 2
    assert result['baseline']['visual_observation_available'] is True


@pytest.mark.parametrize('mutation', ['bytes', 'task'])
def test_roi_changed_or_from_other_task_never_sent(baseline, mutation):
    region = image_region(baseline)
    if mutation == 'bytes':
        (baseline.root / region['path']).write_bytes(b'tampered')
    else:
        region['task_id'] = 'wrong-task'
        baseline.tasks.save_runtime(baseline.task['task_id'], 0, selected_regions=[region])
    client = FakeClient()
    with pytest.raises(ValidationError, match='QUERY_REGION_CHANGED_OR_WRONG_TASK'):
        pb.ProductRAG(baseline.tasks, client=client).run(baseline.task['task_id'], '识别图片')
    assert not client.calls and not client.images


def test_cached_original_source_still_checks_hash(baseline):
    client = FakeClient();product = pb.ProductRAG(baseline.tasks, client=client)
    product.run(baseline.task['task_id'], '甘蓝介绍')
    (baseline.root / 'wiki.html').write_text('changed source bytes')
    with pytest.raises(ValidationError, match='SOURCE_CHANGED'):
        product.run(baseline.task['task_id'], '继续介绍')
    assert len(client.calls) == 1


def test_cancel_after_vision_retains_discarded_response_and_stops_text_call(baseline):
    image_region(baseline)
    def cancel(_):
        task = baseline.tasks.get(baseline.task['task_id'])
        baseline.tasks.cancel(task['task_id'], task['revision'])
    client = FakeClient(after_call=cancel)
    with pytest.raises(ValidationError, match='STALE_TASK_OR_CANCELLED'):
        pb.ProductRAG(baseline.tasks, client=client).run(baseline.task['task_id'], '看看图片')
    task = baseline.tasks.get(baseline.task['task_id'])
    assert task['status'] == 'CANCELLED' and 'answer' not in task and len(client.calls) == 1
    discarded = baseline.tasks.events(task['task_id'])[-1]
    assert discarded['phase'] == 'vision_response' and discarded['response']['status'] == 'OK'


def test_provider_failure_preserved_and_not_candidate_answer(baseline):
    failure = {'status': 'API_ERROR', 'reason': 'HTTP_429', 'call_number': 123}
    client = FakeClient(final_response=failure)
    result = pb.ProductRAG(baseline.tasks, client=client).run(baseline.task['task_id'], '介绍甘蓝')
    assert result['status'] == 'MODEL_ERROR'
    assert result['baseline']['final_model_response'] == failure
    assert baseline.tasks.get(baseline.task['task_id'])['answer']['status'] == 'MODEL_ERROR'


def test_vision_failure_retained_as_explicit_partial(baseline):
    image_region(baseline)
    client = FakeClient(vision_failure=True)
    result = pb.ProductRAG(baseline.tasks, client=client).run(baseline.task['task_id'], '识别物品')
    assert result['status'] == 'BASELINE_PARTIAL'
    assert result['baseline']['degradation_reason'] == 'VISION_MODEL_FAILED'
    assert result['baseline']['vision_observation']['reason'] == 'FIXTURE_VISION_FAILURE'
    assert 'VISUAL_OBSERVATION_UNAVAILABLE' in client.calls[-1][0][-1]['content']


@pytest.mark.parametrize('content', ['not JSON', '{"answer_text":"wrong refs","claim_evidence_refs":["source_chunk:unknown"]}',
    '{"answer_text":"schema wrong","claim_evidence_refs":"source_chunk:fake"}', '{"answer_text":7}'])
def test_malformed_or_uncited_reference_never_success(baseline, content):
    client = FakeClient(final_response={'status': 'OK', 'content': content})
    result = pb.ProductRAG(baseline.tasks, client=client).run(baseline.task['task_id'], '介绍甘蓝')
    assert result['status'] == 'MODEL_ERROR'
    assert result['baseline']['final_model_response']['content'] == content


def test_formal_product_blocked_without_model_call(baseline):
    task = baseline.tasks.create(baseline.snapshot.id, 'released')
    client = FakeClient()
    with pytest.raises(ValidationError, match='PRODUCT_BASELINE_EXPLORATORY_ONLY'):
        pb.ProductRAG(baseline.tasks, client=client).run(task['task_id'], '正式测评')
    assert not client.calls and not baseline.snapshots


def test_product_counts_full_visible_source_and_image_envelope(baseline):
    from stardew_agent.evidence_payload import chars, BUDGET_DEFINITION_HASH
    image_region(baseline)
    client=FakeClient();product=pb.ProductRAG(baseline.tasks,client=client)
    chunks=[{'id':f'source_chunk:{i}','page_id':'Kale','text':'fixture prose '+('x'*1750),
             'locator':'row '+('y'*120),'url':'https://example.test/'+('z'*120),'source_sha256':'fixture'} for i in range(3)]
    assert sum(len(c['text']) for c in chunks)<6000
    product.source_chunks=lambda snapshot:chunks
    result=product.run(baseline.task['task_id'],'根据资料解释甘蓝')
    payload=result['baseline']['model_payload'];receipt=result['baseline']['budget_receipt']
    assert len(payload['source_chunks'])<3
    assert chars(payload)<=6000 and receipt['model_visible_evidence_chars']==chars(payload)
    assert receipt['budget_definition_hash']==BUDGET_DEFINITION_HASH
    packet=json.loads(client.calls[0][0][-1]['content'][0]['text'])
    assert packet['evidence']==payload and payload['image_evidence'][0]['role']=='user_roi'
