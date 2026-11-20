"""Evaluation protocol CLI. No online call without `run --online`."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from stardew_agent.core import ValidationError, read, digest, file_hash, rows as jsonl_rows
from stardew_agent.evaluation_protocol import (
    SCHEMA, METHODS, load_protocol, validate_protocol, export_review, freeze_protocol,
    run_cases, score_run, compare_runs, exclusive_write,
)


def prepare_legacy(output):
    """Copy the original question material; never edit or approve the old set."""
    original = ROOT / 'evaluation/gold/v3_60_candidates.json'
    rows = read(original)
    cases, sources = [], {}
    for row in rows:
        turns = row.get('turns') or [row['question']]
        refs = []
        for e in row.get('source_evidence', []):
            key = e['id']
            sources[key] = {**e, 'kind': 'text_evidence', 'id': key}
            refs.append(key)
        inputs = [{'message': message, 'requires_image': row['category'] == 'visual' or (row['id'] == 'V3-53' and i == 0),
                   'image_ids': []} for i, message in enumerate(turns)]
        goals = [{'id': row['id'] + ':final', 'turn': len(turns) - 1, 'kind': 'knowledge',
                  'description': '完整上下文下的最终答案与任务要求，待独立审核。',
                  'reference_candidate': row['expected_answer_candidate'], 'requires_answer_review': True}]
        for i in range(len(turns) - 1):
            goals.append({'id': row['id'] + f':turn-{i + 1}', 'turn': i, 'kind': 'knowledge',
                          'description': '本轮应答、澄清条件和状态变化需要从原始问题独立标注，尚未批准。',
                          'requires_answer_review': True})
        cases.append({'id': row['id'], 'category': row['category'], 'turns': inputs, 'expected_goals': goals,
                      'source_refs': refs, 'split': 'development', 'expected_origin': 'assistant_authored_pending_review',
                      'independence': 'post_implementation_development', 'claim_scope': 'candidate_submission_set',
                      'legacy_reference_method': row['reference_method'], 'legacy_case_hash': digest(row),
                      'interaction_requirements': row.get('interaction_requirements', []),
                      'review_status': 'PENDING_HUMAN'})
    out = Path(output)
    exclusive_write(out / 'cases.json', cases)
    exclusive_write(out / 'sources.json', list(sources.values()))
    p = read(ROOT / 'evaluation/protocols/post_midterm.json')
    p.update(dataset_id='legacy60-complete-turn-review-v1', cases_path=str((out / 'cases.json').resolve()),
             sources_path=str((out / 'sources.json').resolve()), legacy_original_hash=__import__('hashlib').sha256(original.read_bytes()).hexdigest())
    exclusive_write(out / 'protocol.json', p)
    return export_review(load_protocol(out / 'protocol.json'), out / 'review')


def prepare_visual(output, snapshot_id):
    """Attach existing real capture bytes to a new diagnostic version, not new gold."""
    if not snapshot_id:
        raise ValidationError('VISUAL_PREPARATION_REQUIRES_EXPLICIT_SNAPSHOT')
    from stardew_agent.knowledge import Snapshot
    Snapshot(snapshot_id, allow_candidate=True)
    original = load_protocol(ROOT / 'evaluation/protocols/post_midterm.json')
    cases = json.loads(json.dumps(original['cases']))
    sources = json.loads(json.dumps(original['sources']))
    crop_manifest = ROOT / 'verification/data/visual_test_manifest.jsonl'
    capture_manifest = ROOT / 'verification/data/external_screenshot_manifest.jsonl'
    crops = jsonl_rows(crop_manifest)
    captures = {row['capture_id']: row for row in jsonl_rows(capture_manifest) if row['status'] == 'DOWNLOADED'}
    groups = {}
    for capture_id, capture in captures.items():
        path = 'verification/' + capture['path']
        if file_hash(ROOT / path) != capture['sha256']:
            raise ValidationError('REUSED_CAPTURE_BYTES_CHANGED:' + capture_id)
        groups[capture_id] = {'capture_group': capture_id, 'split': 'development', 'query_ids': [],
                             'source_sha256': capture['sha256'], 'claim_scope': 'diagnostic_reused_capture'}
        sources.append({'id': 'capture:' + capture_id, 'kind': 'real_screenshot', 'image_role': 'original_capture',
            'path': path, 'sha256': capture['sha256'], 'capture_group': capture_id, 'split': 'development',
            'claim_scope': 'diagnostic_reused_capture', 'review_status': 'PENDING_HUMAN',
            'source_page': capture['source_page'], 'image_url': capture['image_url'],
            'game_version': capture['game_version'], 'mod_status': capture['mod_status'],
            'redistribution': capture['redistribution'], 'retrieved_at': capture['retrieved_at']})
    for crop in crops:
        parent = captures[crop['capture_id']]
        path = 'verification/' + crop['path']
        if file_hash(ROOT / path) != crop['sha256'] or crop['source_sha256'] != parent['sha256']:
            raise ValidationError('REUSED_ROI_PROVENANCE_CHANGED:' + crop['sample_id'])
        image_id = 'query:' + crop['sample_id']
        groups[crop['capture_id']]['query_ids'].append(image_id)
        sources.append({'id': image_id, 'kind': 'real_screenshot', 'image_role': 'query_roi',
            'path': path, 'sha256': crop['sha256'], 'capture_group': crop['capture_id'], 'split': 'development',
            'claim_scope': 'diagnostic_reused_capture', 'legacy_declared_split': crop['split'],
            'parent_capture_id': 'capture:' + crop['capture_id'], 'parent_sha256': parent['sha256'],
            'bbox_original_pixels': crop['bbox'], 'source_page': crop['source_page'],
            'draft_labels': crop['labels'], 'draft_ambiguous': crop['ambiguous'],
            'draft_unknown_under_legacy_gallery': crop['unknown'], 'draft_note': crop['note'],
            'label_origin': 'legacy_assistant_visual_review', 'review_status': 'PENDING_HUMAN',
            'human_approval': None, 'game_version': crop['game_version'], 'mod_status': parent['mod_status']})
    assignments = {'PM-09': ('query:V01', ['source:Parsnip'], ['Parsnip', '防风草']),
                   'PM-10': ('query:V10', ['source:Melon'], ['Melon', '甜瓜', 'Melon_Stage_3'])}
    for case in cases:
        if case['id'] not in assignments:
            continue
        image_id, references, hidden_labels = assignments[case['id']]
        case['turns'][0]['image_ids'] = [image_id]
        case['turns'][0]['roi'] = [0, 0, 1, 1]
        case['source_refs'] = references + [image_id]
        case['hidden_identity_labels'] = hidden_labels
        case['visual_sample_scope'] = 'diagnostic_reused_capture'
        case['input_preparation_note'] = 'Existing query ROI reused; all questions and expected goals remain unchanged. Draft labels are offline only and require independent human review.'
    assert all(new['expected_goals'] == old['expected_goals'] and [t['message'] for t in new['turns']] == [t['message'] for t in old['turns']]
               for new, old in zip(cases, original['cases']))
    out = Path(output)
    protocol = json.loads(json.dumps(original['protocol']))
    protocol.update(dataset_id='post-midterm-product-diagnostics-visual-ready-v2', version=2,
        cases_path=str((out / 'cases.json').resolve()), sources_path=str((out / 'sources.json').resolve()),
        knowledge_snapshot_id=snapshot_id, status='CANDIDATE_INPUTS_AVAILABLE_HUMAN_REVIEW_PENDING',
        parent_protocol_hashes=original['hashes'])
    protocol['visual_policy']['query_set_scope'] = 'diagnostic_reused_capture'
    protocol['limits'] = ['12 post-implementation exploratory cases; no blind or independent accuracy claim.',
        'PM-09 and PM-10 reuse previously evaluated capture families; all 35 prior crops are grouped as development.',
        'Question and expected-goal text remain unchanged; PM-09 old missing-image wording records v1 history. Input availability is recorded in input_audit.json.',
        'Draft legacy labels and source metadata are not human approvals and are never passed to the Agent.',
        'Original v1 and legacy60 artifacts remain unchanged; the nine old missing-image interactions are not all completed by this version.',
        'Knowledge, rules, semantic gold and answer outcomes each still require the appropriate independent review.',
        'Product baseline remains exploratory; formal product comparison protocol not approved.']
    audit = {'status': 'CANDIDATE_INPUTS_PREPARED_NOT_SCORED', 'parent_protocol_hashes': original['hashes'],
        'crop_manifest_sha256': file_hash(crop_manifest), 'capture_manifest_sha256': file_hash(capture_manifest),
        'snapshot_id': snapshot_id, 'questions_changed': 0, 'expected_goals_changed': 0,
        'attached_query_cases': {key: row[0] for key, row in assignments.items()},
        'source_captures': len(captures), 'source_crop_rows': len(crops), 'new_independent_captures': 0,
        'legacy60_missing_image_interactions_unchanged': 9, 'human_approvals_created': 0}
    for name, body in [('cases.json', cases), ('sources.json', sources), ('protocol.json', protocol),
                       ('capture_groups.json', list(groups.values())), ('input_audit.json', audit)]:
        exclusive_write(out / name, body)
    result = export_review(load_protocol(out / 'protocol.json'), out / 'review')
    return {**result, 'input_preparation': audit, 'protocol': str(out / 'protocol.json')}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('validate', 'export-review', 'freeze', 'run', 'score', 'compare', 'prepare-legacy', 'prepare-visual'))
    parser.add_argument('--protocol', default='evaluation/protocols/post_midterm.json')
    parser.add_argument('--output')
    parser.add_argument('--gold-reviews')
    parser.add_argument('--knowledge-manifest')
    parser.add_argument('--frozen')
    parser.add_argument('--run')
    parser.add_argument('--judgments')
    parser.add_argument('--scores', nargs='+')
    parser.add_argument('--mode', choices=('exploratory', 'formal'), default='exploratory')
    parser.add_argument('--method', choices=METHODS, default='D')
    parser.add_argument('--comparison-family', choices=('structure_ablation', 'product_workflow'))
    parser.add_argument('--case', dest='case_ids', action='append')
    parser.add_argument('--snapshot')
    parser.add_argument('--online', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.command in ('prepare-legacy', 'prepare-visual'):
            if not args.output:
                raise ValidationError('OUTPUT_REQUIRED')
            result = prepare_legacy(args.output) if args.command == 'prepare-legacy' else prepare_visual(args.output, args.snapshot)
        elif args.command == 'compare':
            result = compare_runs([read(p) for p in (args.scores or [])])
            if args.output:
                exclusive_write(args.output, result)
        else:
            bundle = load_protocol(args.protocol)
            if args.command == 'validate':
                result = validate_protocol(bundle)
                if args.output:
                    exclusive_write(args.output, result)
            elif args.command == 'export-review':
                if not args.output:
                    raise ValidationError('OUTPUT_REQUIRED')
                result = export_review(bundle, args.output)
            elif args.command == 'freeze':
                if not all((args.output, args.gold_reviews, args.knowledge_manifest)):
                    raise ValidationError('FREEZE_REQUIRES_OUTPUT_GOLD_REVIEWS_AND_KNOWLEDGE_MANIFEST')
                result = freeze_protocol(bundle, args.gold_reviews, args.knowledge_manifest, args.output)
            elif args.command == 'run':
                if not args.output:
                    raise ValidationError('OUTPUT_DIRECTORY_REQUIRED')
                live_factory = None
                if args.method == 'product':
                    from stardew_agent.product_baseline import make_live_product
                    live_factory = make_live_product
                result = run_cases(bundle, args.output, method=args.method, mode=args.mode, snapshot_id=args.snapshot,
                                   case_ids=args.case_ids, online=args.online, frozen_path=args.frozen,
                                   live_factory=live_factory, comparison_family=args.comparison_family)
                # The full answers and traces are saved, not repeated in console.
                result = {k: v for k, v in result.items() if k != 'rows'}
            else:
                if not args.run:
                    raise ValidationError('RUN_FILE_REQUIRED')
                result = score_run(bundle, read(args.run), judgments=read(args.judgments) if args.judgments else None)
                if args.output:
                    exclusive_write(args.output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get('status') in ('FAIL', 'PARTIAL', 'PENDING_HUMAN', 'EXPLORATORY_OR_PENDING_REVIEW', 'CODE_CHANGED', 'MODEL_CONFIG_CHANGED', 'BUDGET_CONTRACT_VIOLATION') else 0
    except (ValueError, KeyError, OSError) as exc:
        print(json.dumps({'status': 'BLOCKED', 'reason': str(exc), 'error_type': type(exc).__name__}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
