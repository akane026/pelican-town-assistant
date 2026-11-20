"""Fresh-process snapshot/evidence smoke. No provider call or human approval."""
import argparse,os,platform,resource,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stardew_agent.core import ROOT,read,write,file_hash,ValidationError
from stardew_agent.knowledge import Snapshot
from stardew_agent.evidence import BundleStore
from stardew_agent.retrieval import Retriever
from stardew_agent.rules import dependencies,missing_dependencies
from stardew_agent.calculations import execute

def main():
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    dest=ROOT/args.output
    if dest.exists():raise ValidationError('REPRO_OUTPUT_EXISTS')
    started=time.perf_counter();snapshot=Snapshot(args.snapshot,allow_candidate=True);roundtrip=snapshot.roundtrip()
    baseline=read(ROOT/'artifacts/v3/post_midterm/baseline.json');protected={k:v for k,v in baseline['files'].items() if k.startswith(('data/snapshots/','data/manifests/'))}
    changed=[path for path,sha in protected.items() if file_hash(ROOT/path)!=sha]
    retriever=Retriever(snapshot);store=BundleStore();cases=[]
    # Explicit arithmetic fixture from frozen cited values, not general accuracy.
    for entity,quantity,expected in [('entity:Kale',3,330),('entity:Cauliflower',3,525)]:
        params={'entity_id':entity,'quantity':quantity,'quality':'normal','profession':'none'}
        result=retriever.retrieve('直接出售价值',entity_ids=[entity],task_id='repro:'+str(os.getpid()),revision=1,candidate=True)
        for _ in range(4):
            bundle=store.get(result['bundle_id'],task_id='repro:'+str(os.getpid()),revision=1,snapshot_id=snapshot.id)
            dep=dependencies('sale_value',params,bundle.data());missing=missing_dependencies(bundle.data(),dep['selectors'])
            if not missing and not dep.get('dependency_discovery_incomplete'):break
            result=retriever.supplement(bundle,missing,candidate=True)
        receipt=execute('sale_value',bundle,params)
        cases.append({'entity_id':entity,'expected_from_explicit_arithmetic':expected,'receipt':receipt,'passed':receipt.get('outputs',{}).get('sales_g')==expected})
    raw_peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report={'status':'PASS' if roundtrip['status']=='PASS' and not changed and all(c['passed'] for c in cases) else 'FAIL',
        'snapshot_id':snapshot.id,'roundtrip':roundtrip,'protected_files_checked':len(protected),'changed_protected_files':changed,
        'arithmetic_smoke':cases,'python':sys.version,'executable':sys.executable,'platform':platform.platform(),
        'elapsed_seconds':time.perf_counter()-started,'peak_rss_mib':raw_peak/(1024**2 if sys.platform=='darwin' else 1024),
        'network_called':False,'execution_mode':'fresh_process_frozen_snapshot_diagnostic',
        'limitations':['Two arithmetic smoke cases do not establish semantic accuracy.','No new independent user or screenshot study.','Human knowledge/rule/gold review remains pending.']}
    write(dest,report);print({k:report[k] for k in ('status','snapshot_id','protected_files_checked','elapsed_seconds','peak_rss_mib')});return 0 if report['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
