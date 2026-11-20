"""Replay the existing 35 public screenshot crops as reused-development diagnostics.

No collection, threshold tuning, model call, label correction or human approval.
The inherited dev/test column is retained as provenance, never used as a claim
that these repeatedly inspected captures are an untouched evaluation split.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
import json
import math
from pathlib import Path
import re
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from PIL import Image,ImageChops
from stardew_agent.core import ValidationError,digest,file_hash,now
from stardew_agent.knowledge import Snapshot
from stardew_agent.online_vision import VisualMatcher
from verification.vision import DEFAULT_CONFIG

DEFAULT_SNAPSHOT='c704b0819193e793a6f5088b3d2dac57363698cd687bb74e5eb6ae3e8cddf303'
POLICY={
    'split':'reused_development',
    'label_origin':'existing_assistant_visual_review_independent_human_pending',
    'ground_truth_independently_reviewed':False,
    'formal_score':False,
    'threshold_tuning':'none; unchanged verification.vision.DEFAULT_CONFIG',
    'network_calls':0,'model_calls':0,'automatic_identity_confirmation_expected':False,
    'unknown_cohort':'Legacy empty-label samples; not verified as outside the expanded current gallery.',
}

def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]

def safe_json(value):
    if isinstance(value,float) and not math.isfinite(value):return str(value)
    if isinstance(value,dict):return {k:safe_json(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [safe_json(v) for v in value]
    return value

def exclusive_json(path,value):
    with Path(path).open('x') as out:json.dump(safe_json(value),out,ensure_ascii=False,indent=2,allow_nan=False)

def legacy_path(value):
    path=(ROOT/'verification'/value).resolve()
    if not path.is_relative_to(ROOT/'verification'):raise ValidationError('LEGACY_PATH_OUTSIDE_VERIFICATION')
    return path

def map_legacy_label(label,snapshot):
    """Only schema identity is consulted here; no predictions/images are inputs."""
    match=re.fullmatch(r'(.+)_Stage_(\d+)',label)
    if match:
        crop_id='entity:'+match.group(1);ordinal=int(match.group(2))
        ids=sorted(r['id'] for r in snapshot.domain['entities']
                   if r['type']=='CropStage' and r.get('crop_id')==crop_id and r.get('ordinal')==ordinal)
        rule={'kind':'CropStage','crop_id':crop_id,'ordinal':ordinal,
              'match_fields':['type','crop_id','ordinal'],'namespace_policy':'unique matching namespace required'}
    else:
        # Exact entity namespace conversion is still defined when the current
        # snapshot lacks that entity. Keep such known-label samples as misses,
        # rather than dropping them from the denominator after seeing coverage.
        eid='entity:'+label;ids=[eid]
        rule={'kind':'exact_entity_id','entity_id':eid,'match_fields':['id']}
    return {'legacy_label':label,'mapping_rule':rule,'mapped_entity_ids':ids,
            'status':'MAPPED_UNIQUE' if len(ids)==1 else 'UNRESOLVED' if not ids else 'AMBIGUOUS_NAMESPACE',
            'mapped_ids_present_in_snapshot':[eid for eid in ids if eid in snapshot.records['entities']],
            'uses_prediction':False}

def validate_input(sample,source):
    query=legacy_path(sample['path']);original=legacy_path(source['path'])
    if file_hash(query)!=sample['sha256']:raise ValidationError('QUERY_HASH_CHANGED')
    if file_hash(original)!=source['sha256'] or source['sha256']!=sample['source_sha256']:raise ValidationError('SOURCE_HASH_CHANGED')
    box=sample['bbox']
    if not isinstance(box,list) or len(box)!=4 or any(type(v)!=int for v in box):raise ValidationError('INVALID_LEGACY_PIXEL_BBOX')
    with Image.open(original) as image,Image.open(query) as cropped:
        if not (0<=box[0]<box[2]<=image.width and 0<=box[1]<box[3]<=image.height):raise ValidationError('BBOX_OUTSIDE_SOURCE')
        expected=image.convert('RGB').crop(box);actual=cropped.convert('RGB')
        if actual.size!=expected.size or ImageChops.difference(actual,expected).getbbox():raise ValidationError('CROP_SOURCE_PIXEL_MISMATCH')
        return {'query_path':str(query),'source_path':str(original),'query_sha256':file_hash(query),
                'source_sha256':file_hash(original),'query_dimensions':list(actual.size),'source_dimensions':list(image.size),
                'bbox_original_pixels':box,'crop_matches_source_pixels':True}

def metrics(rows):
    executed=[r for r in rows if r['execution_status']=='EXECUTED']
    known=[r for r in rows if r['legacy_labels']]
    scorable=[r for r in known if r['label_mapping_status']=='MAPPED_UNIQUE']
    legacy_unknown=[r for r in rows if not r['legacy_labels']]
    gallery_known=[r for r in scorable if r['mapped_ids_in_current_gallery']]
    absent_known=[r for r in scorable if not r['mapped_ids_in_current_gallery']]
    latencies=[r['latency_ms'] for r in executed]
    ranked=sorted(latencies)
    return {
        'samples':len(rows),'executed':len(executed),'input_or_execution_errors':len(rows)-len(executed),
        'known_legacy_labels':len(known),'known_mapping_scorable':len(scorable),
        'known_mapping_unresolved':len(known)-len(scorable),
        'known_labels_present_in_gallery':len(gallery_known),'known_labels_absent_from_gallery':len(absent_known),
        'known_absent_from_gallery_sample_ids':[r['sample_id'] for r in absent_known],
        'known_absent_from_gallery_status_counts':dict(Counter(r.get('status','NOT_EXECUTED') for r in absent_known)),
        'known_candidate_top1_hits':sum(r.get('top1_label_match') is True for r in scorable),
        'known_candidate_top3_hits':sum(r.get('top3_label_match') is True for r in scorable),
        'known_candidate_top1_fraction':sum(r.get('top1_label_match') is True for r in scorable)/len(scorable) if scorable else None,
        'known_candidate_top3_fraction':sum(r.get('top3_label_match') is True for r in scorable)/len(scorable) if scorable else None,
        'known_in_gallery_top1_hits':sum(r.get('top1_label_match') is True for r in gallery_known),
        'known_in_gallery_top3_hits':sum(r.get('top3_label_match') is True for r in gallery_known),
        'legacy_unknown_count':len(legacy_unknown),
        'legacy_unknown_status_counts':dict(Counter(r.get('status','NOT_EXECUTED') for r in legacy_unknown)),
        'current_out_of_gallery_ground_truth':'UNVERIFIED; legacy unknown labels are not reinterpreted',
        'status_counts':dict(Counter(r.get('status','NOT_EXECUTED') for r in rows)),
        'returned_candidate_count_distribution':dict(Counter(str(len(r.get('top3',[]))) for r in rows)),
        'queries_with_shared_pixel_candidate':sum(any(c.get('shared_pixels') for c in r.get('top3',[])) for r in rows),
        'queries_with_shared_pixel_top1':sum(bool(r.get('top3') and r['top3'][0].get('shared_pixels')) for r in rows),
        'threshold_pass_count':sum(r.get('threshold_pass') is True for r in rows),
        'automatic_confirmation_count':sum(r.get('automatic_identity_confirmation') is True for r in rows),
        'automatic_confirmation_coverage':sum(r.get('automatic_identity_confirmation') is True for r in rows)/len(rows) if rows else None,
        'latency_median_ms':statistics.median(latencies) if latencies else None,
        'latency_p95_ms_nearest_rank':ranked[max(0,math.ceil(.95*len(ranked))-1)] if ranked else None,
        'metric_scope':'Candidate retrieval agreement with reused assistant labels; not automatic recognition accuracy or a formal score.'}

def review_markdown(rows,summary):
    m=summary['overall'];lines=[
        '# 真实截图裁剪：候选检索人工核对索引','',
        '全部样本属于 **reused_development**。旧标签由助手标注，仍待独立人工审核；本表没有任何人工批准或正式成功率。',
        f"保留 {len(rows)} 个原有裁剪、{summary['capture_groups']} 个来源组；有标签候选 Top-1 命中 {m['known_candidate_top1_hits']}/{m['known_mapping_scorable']}、Top-3 命中 {m['known_candidate_top3_hits']}/{m['known_mapping_scorable']}。这些仅是候选与旧标签的相符计数。",
        '原 unknown 队列没有新补标签，扩展图库后不能把它直接视为当前库外真值。所有候选仍需用户确认，数量、品质和游戏版本未核验。',
        '原图链接用于查看完整上下文；ROI 为既有裁剪；候选图片为对应图库资产，JSON 同时保存其 region_id/bbox，复合资产应按 bbox 核对。','',
        '| 样本 / 来源原图 | 原 ROI 与旧标签 | 候选一 | 候选二 | 候选三 | 状态与待审点 |',
        '| --- | --- | --- | --- | --- | --- |']
    for row in rows:
        source=f"{row['sample_id']} · {row['capture_group']}<br>[原图](<{row.get('source_path','')}>) · [来源页面]({row['source_page']})"
        query=f"![{row['sample_id']} ROI](<{row.get('query_path','')}>)<br>旧标签：{', '.join(row['legacy_labels']) or 'UNKNOWN（沿用旧空标签）'}"
        candidates=[]
        for c in row.get('top3',[]):
            candidates.append(f"![候选图](<{c['asset_path']}>)<br>{c['entity_id']}<br>距离 {c['distance']}；共享像素：{c['shared_pixels']}")
        candidates+=['—']*(3-len(candidates))
        note=f"{row.get('status',row['execution_status'])}<br>原备注：{row['legacy_record'].get('note','')}<br>标签、身份及阶段待人工核对"
        lines.append('| '+' | '.join([source,query,*candidates,note]).replace('\n',' ')+' |')
    lines+=['','完整记录见 [predictions.jsonl](predictions.jsonl)、[label_mapping.json](label_mapping.json) 与 [summary.json](summary.json)。',
            '未下载、未生成新查询图片、未重新调阈值、未调用模型；原始 split 只留作来源记录，不构成独立测试划分。','']
    return '\n'.join(lines)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshot',default=DEFAULT_SNAPSHOT)
    p.add_argument('--manifest',default='verification/data/visual_test_manifest.jsonl')
    p.add_argument('--sources',default='verification/data/external_screenshot_manifest.jsonl')
    p.add_argument('--output',required=True)
    args=p.parse_args(argv)
    manifest=ROOT/args.manifest;sources_path=ROOT/args.sources;out=ROOT/args.output
    if out.exists():raise ValidationError('OUTPUT_ALREADY_EXISTS')
    samples=read_rows(manifest);sources={r['capture_id']:r for r in read_rows(sources_path)}
    if len(samples)!=35 or len({s['sample_id'] for s in samples})!=35:raise ValidationError('EXPECTED_COMPLETE_EXISTING_35_SAMPLE_SET')
    snapshot=Snapshot(args.snapshot,allow_candidate=True)
    # Freeze mapping BEFORE generating any prediction. No label is inferred
    # from a candidate, original note or a filename returned by the matcher.
    mapping={label:map_legacy_label(label,snapshot) for label in sorted({label for s in samples for label in s['labels']})}
    code_paths=[Path(__file__).resolve(),ROOT/'stardew_agent/online_vision.py',ROOT/'verification/vision.py']
    code_before={str(path.relative_to(ROOT)):file_hash(path) for path in code_paths}
    out.mkdir(parents=True)
    exclusive_json(out/'label_mapping.json',{'snapshot_id':snapshot.id,'mapping':mapping,'mapping_sha256':digest(mapping),
        'mapping_generated_before_predictions':True,'label_manifest_sha256':file_hash(manifest),'policy':POLICY})
    exclusive_json(out/'input_manifest.json',{'manifest_path':str(manifest),'manifest_sha256':file_hash(manifest),
        'source_manifest_path':str(sources_path),'source_manifest_sha256':file_hash(sources_path),
        'samples':samples,'sources':[sources[c] for c in sorted({s['capture_id'] for s in samples})]})
    matcher=VisualMatcher(snapshot);config_before=copy.deepcopy(matcher.config)
    if config_before!=DEFAULT_CONFIG:raise ValidationError('VISUAL_DEFAULT_CONFIG_CHANGED')
    gallery_targets={t['entity']['id'] for row in matcher.gallery.values() for t in row['targets'].values()}
    gallery={'pixel_groups':len(matcher.gallery),'target_ids':sorted(gallery_targets),
             'shared_pixel_groups':sum(len(r['targets'])>1 for r in matcher.gallery.values()),
             'targets_sha256':digest(sorted(gallery_targets))}
    exclusive_json(out/'run_config.json',{'created_at':now(),'snapshot_id':snapshot.id,'snapshot_manifest_sha256':file_hash(snapshot.directory/'manifest.json'),
        'config':config_before,'config_sha256':digest(config_before),'code_manifest':code_before,'gallery':gallery,'policy':POLICY})
    results=[];started=time.perf_counter()
    with (out/'predictions.jsonl').open('x') as predictions:
        for sample in samples:
            source=sources[sample['capture_id']];mapped=[mapping[l] for l in sample['labels']]
            unique=bool(mapped) and all(m['status']=='MAPPED_UNIQUE' for m in mapped)
            expected=sorted({eid for m in mapped for eid in m['mapped_entity_ids']})
            row={'sample_id':sample['sample_id'],'split':'reused_development','legacy_split':sample.get('split'),
                 'capture_group':sample['capture_id'],'source_page':sample['source_page'],'legacy_labels':sample['labels'],
                 'legacy_label_hash':digest(sample['labels']),'legacy_record_hash':digest(sample),'legacy_record':sample,
                 'label_mapping_status':'MAPPED_UNIQUE' if unique else 'LEGACY_UNKNOWN' if not mapped else 'UNRESOLVED_OR_AMBIGUOUS',
                 'mapped_expected_ids':expected,'mapped_ids_in_current_gallery':[e for e in expected if e in gallery_targets],
                 'label_review_status':'ASSISTANT_LABELS_HUMAN_REVIEW_PENDING','kind_supplied':sample['kind'],
                 'current_open_set_truth':'UNVERIFIED' if not mapped else None,'top1_label_match':None,'top3_label_match':None}
            try:
                row.update(validate_input(sample,source))
                prediction=matcher.match(Path(row['query_path']),sample['kind'])
                candidates=[]
                for candidate in prediction['candidates']:
                    asset=snapshot.records['assets'][candidate['asset_id']];region=snapshot.records['regions'][candidate['region_id']]
                    candidates.append({**candidate,'asset_path':str(ROOT/asset['path']),'asset_sha256':asset['sha256'],
                                       'gallery_region_bbox':region['bbox'],'gallery_entity_type':snapshot.records['entities'][candidate['entity_id']]['type']})
                row.update(execution_status='EXECUTED',status=prediction['status'],top3=candidates,
                    latency_ms=prediction['elapsed_seconds']*1000,threshold_pass=prediction['threshold_pass'],
                    automatic_identity_confirmation=prediction['automatic_identity_confirmation'],matcher_result=prediction)
                if unique:
                    row['top1_label_match']=bool(candidates and candidates[0]['entity_id'] in expected)
                    row['top3_label_match']=bool(set(expected)&{c['entity_id'] for c in candidates})
            except (ValueError,KeyError,TypeError,OSError) as exc:
                row.update(execution_status='INPUT_OR_EXECUTION_ERROR',error_type=type(exc).__name__,error=str(exc),top3=[])
            results.append(row);predictions.write(json.dumps(safe_json(row),ensure_ascii=False,allow_nan=False)+'\n');predictions.flush()
            print(json.dumps({'sample_id':row['sample_id'],'status':row.get('status',row['execution_status']),'candidate_count':len(row['top3'])},ensure_ascii=False),flush=True)
    code_after={str(path.relative_to(ROOT)):file_hash(path) for path in code_paths}
    summary={'status':'EXECUTED_DIAGNOSTIC_HUMAN_PENDING','snapshot_id':snapshot.id,'policy':POLICY,'overall':metrics(results),
        'by_kind':{kind:metrics([r for r in results if r['kind_supplied']==kind]) for kind in sorted({r['kind_supplied'] for r in results})},
        'capture_groups':len({r['capture_group'] for r in results}),'capture_group_counts':dict(Counter(r['capture_group'] for r in results)),
        'label_mapping_sha256':digest(mapping),'manifest_sha256':file_hash(manifest),'query_hashes_sha256':digest([(r['sample_id'],r.get('query_sha256')) for r in results]),
        'config_sha256':digest(config_before),'config_unchanged':matcher.config==config_before,'code_changed':code_before!=code_after,
        'all_original_samples_retained':len(results)==len(samples),'elapsed_seconds':time.perf_counter()-started,'gallery':gallery,
        'formal_success_rate':None,'automatic_recognition_accuracy':None,'independent_human_review_performed':False,
        'limitations':['Repeatedly used development captures; original dev/test labels are historical metadata only.',
            'All labels remain assistant-authored and human-review pending; ambiguous stages are retained.',
            'Legacy empty labels do not prove current out-of-gallery truth after gallery expansion.',
            'Known-item candidate rank agreement is not automatic confirmation performance.',
            'Game versions, possible mods, collection-menu differences, count/quality interpretation remain unverified.',
            'Pixels are existing local research inputs; no new download or redistribution authorization is implied.']}
    if summary['overall']['input_or_execution_errors'] or summary['code_changed'] or not summary['config_unchanged']:summary['status']='PARTIAL_DIAGNOSTIC'
    exclusive_json(out/'summary.json',summary)
    (out/'人工核对索引.md').write_text(review_markdown(results,summary))
    print(json.dumps({k:v for k,v in summary.items() if k not in ('gallery','by_kind')},ensure_ascii=False,indent=2))
    return 0 if summary['status']=='EXECUTED_DIAGNOSTIC_HUMAN_PENDING' else 2

if __name__=='__main__':raise SystemExit(main())
