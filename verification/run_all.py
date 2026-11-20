"""Recompute core verification offline; never install, download or call models."""
from __future__ import annotations
import argparse
import os
import socket
import subprocess
import sys
import time
from datetime import datetime,timezone
from .common import BASE, DATA, ROOT, dump, file_sha, load, now, offline_guard


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--offline',action='store_true');args=parser.parse_args()
    if not args.offline:parser.error('Use --offline; online collection/model calls are separate explicit commands')
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');directory=BASE/'results/runs'/run_id;directory.mkdir(parents=True)
    logdir=BASE/'logs/runs'/run_id;logdir.mkdir(parents=True)
    started=now();offline_guard()
    try:socket.getaddrinfo('offline-self-test.invalid',443);network_selfcheck=False
    except RuntimeError:network_selfcheck=True
    stages=[('V01','verification.knowledge',[]),('V02','verification.graph',['V01']),
            ('V03','verification.vision',['V01']),('V04','verification.retrieval',['V02']),
            ('V05','verification.probes.calculation_probe',['V02']),('V07','verification.pipeline',['V02','V03','V04','V05']),
            ('MKG','verification.probes.mkgrag_semantica_probe',['V02','V03','V04','V05'])]
    inputs={str(p.relative_to(ROOT)):file_sha(p) for p in [DATA/'source_manifest.jsonl',DATA/'image_manifest.jsonl',DATA/'external_screenshot_manifest.jsonl',
       DATA/'visual_test_manifest.jsonl',DATA/'retrieval_inputs.jsonl',DATA/'retrieval_gold.jsonl',ROOT/'requirements/verification.lock.txt']}
    code={str(p.relative_to(ROOT)):file_sha(p) for p in sorted((BASE).rglob('*.py')) if '__pycache__' not in str(p)}
    results=[];blocked=set();elapsed_start=time.perf_counter()
    for id,module,deps in stages:
        if blocked&set(deps):
            results.append({'id':id,'status':'BLOCKED','reason':'upstream_failed'});blocked.add(id);continue
        command=[sys.executable,'-m','verification.offline_worker',module,str(directory/(id+'.worker.json'))]
        t=time.perf_counter();r=subprocess.run(command,cwd=ROOT,text=True,capture_output=True,timeout=180)
        (logdir/(id+'.stdout.log')).write_text(r.stdout);(logdir/(id+'.stderr.log')).write_text(r.stderr)
        row={'id':id,'module':module,'command':command,'exit_code':r.returncode,'elapsed_seconds':round(time.perf_counter()-t,3),
           'execution':'recomputed_in_fresh_process','stdout':str((logdir/(id+'.stdout.log')).relative_to(BASE)),
           'stderr':str((logdir/(id+'.stderr.log')).relative_to(BASE)),
           'worker':load(directory/(id+'.worker.json')) if (directory/(id+'.worker.json')).exists() else None}
        results.append(row)
        if r.returncode not in (0,2):blocked.add(id)
        dump(directory/'checkpoint.json',{'run_id':run_id,'stages':results})
        print(id,r.returncode,round(time.perf_counter()-t,2),flush=True)
    outputs={str(p.relative_to(ROOT)):file_sha(p) for p in [BASE/'results/v01.json',BASE/'results/v02.json',BASE/'results/visual_metrics.json',
       BASE/'results/v04.json',BASE/'results/v05.json',BASE/'results/v07.json',BASE/'results/mkgrag_semantica.json',BASE/'artifacts/graph/manifest.json'] if p.exists()}
    models={str(p.relative_to(ROOT)):file_sha(p) for p in [BASE/'results/model_probe.json',BASE/'results/model_visual_pilot.json',BASE/'results/model_reference_pilot.json',BASE/'results/model_workflow.json'] if p.exists()}
    status='FAIL' if blocked or not network_selfcheck else 'PARTIAL'
    result={'run_id':run_id,'started_at':started,'finished_at':now(),'status':status,'exit_code':1 if status=='FAIL' else 2,
      'elapsed_seconds':round(time.perf_counter()-elapsed_start,3),'offline':True,'network_selfcheck_passed':network_selfcheck,
      'git_status':'not_initialized' if not (ROOT/'.git').exists() else 'repository_present_no_commit_claim',
      'input_hashes':inputs,'code_hashes':code,'output_hashes':outputs,'online_evidence_reused_not_reexecuted':models,
      'stages':results,'reason':'Core diagnostic assertions recomputed; full original gates still have sample/version/review gaps',
      'snapshot_id':load(BASE/'artifacts/graph/manifest.json')['snapshot_id'] if (BASE/'artifacts/graph/manifest.json').exists() else None}
    dump(directory/'manifest.json',result);dump(BASE/'results/v08.json',result)
    print('OFFLINE',status,'exit',result['exit_code']);return result['exit_code']

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except FileNotFoundError as exc:
        dump(BASE/'results/v08.json',{'status':'BLOCKED','exit_code':2,'at':now(),'reason':'missing_local_input','path':str(exc.filename)})
        print('BLOCKED missing local input');raise SystemExit(2)
    except (ValueError,KeyError,subprocess.SubprocessError) as exc:
        dump(BASE/'results/v08.json',{'status':'ERROR','exit_code':3,'at':now(),'reason':type(exc).__name__})
        print('ERROR',type(exc).__name__);raise SystemExit(3)
