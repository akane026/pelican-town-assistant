from __future__ import annotations
import argparse,sys,platform
from .core import *

def main(argv=None):
    p=argparse.ArgumentParser(prog='stardew_agent');sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('inspect');i=sub.add_parser('ingest');i.add_argument('--manifest',default='configs/corpus.json')
    b=sub.add_parser('build');b.add_argument('--batch',default='baseline');b.add_argument('--mode',choices=['structural','multimodal'],default='multimodal');b.add_argument('--online',action='store_true');b.add_argument('--offline',action='store_true');b.add_argument('--resume',action='store_true');b.add_argument('--visual-limit',type=int,default=4);b.add_argument('--text-limit',type=int,default=2);b.add_argument('--alignment-limit',type=int,default=2)
    for name in ('review-export','snapshot','publish'):
        q=sub.add_parser(name);q.add_argument('--build-id');q.add_argument('--snapshot-id')
        if name=='publish':q.add_argument('--review',required=True)
    q=sub.add_parser('evaluate');q.add_argument('--suite',choices=['construction','retrieval','agent','formal','visual','reliability'],required=True);q.add_argument('--config',default='evaluation/protocols/v3.json');q.add_argument('--online',action='store_true')
    q=sub.add_parser('serve');q.add_argument('--host',default='127.0.0.1');q.add_argument('--port',type=int,default=8765)
    for name in ('normalize','graph-audit','release-audit'):
        q=sub.add_parser(name);q.add_argument('--snapshot-id');q.add_argument('--output')
        if name=='normalize':q.add_argument('--policy');q.add_argument('--activate',action='store_true')
        if name=='release-audit':q.add_argument('--review')
    a=p.parse_args(argv)
    try:
        if a.command=='serve':
            from .server import serve
            serve(a.host,a.port);return 0
        if a.command=='inspect':
            from importlib.metadata import version
            from .knowledge import Snapshot
            s=Snapshot(allow_candidate=True)
            result={'status':'PASS','python':platform.python_version(),'platform':platform.platform(),'semantica':version('semantica'),'snapshot':s.manifest,
                'model_key_configured':bool(__import__('dotenv').dotenv_values(ROOT/'.env').get('CHATECNU_API_KEY')),'network_called':False,'roundtrip':s.roundtrip()}
        elif a.command=='ingest':
            from .parsing import parse_page
            config=read(contained(ROOT/a.manifest));sources=read(DATA/'manifests/sources.json');assets=read(DATA/'manifests/assets.json')
            checked=[{'page_id':s['page_id'],'source_hash':s['sha256'],'occurrences':len(parse_page(s,assets)['occurrences'])} for s in sources]
            result={'status':'PASS','mode':'validate_legally_acquired_local_sources','network_called':False,'sources':checked,'assets':len(assets),'configured_batches':list(config)}
            write(ARTIFACTS/'ingest/validation.json',result)
        elif a.command=='build':
            if a.online and a.offline:raise ValidationError('ONLINE_OFFLINE_CONFLICT')
            from .construction import build_batch
            result=build_batch(a.batch,a.mode,a.online,a.visual_limit,a.text_limit,a.alignment_limit,a.resume)
        elif a.command in ('review-export','snapshot','publish'):
            from .knowledge import build_snapshot,review_export,publish,Snapshot
            sid=build_snapshot(a.build_id)['snapshot_id'] if a.build_id else a.snapshot_id or Snapshot(allow_candidate=True).id
            result=review_export(sid) if a.command=='review-export' else publish(sid,read(contained(ROOT/a.review))) if a.command=='publish' else Snapshot(sid,allow_candidate=True).manifest
        elif a.command in ('normalize','graph-audit','release-audit'):
            from .knowledge import Snapshot
            s=Snapshot(a.snapshot_id,allow_candidate=True)
            if a.command=='normalize':
                from .knowledge import normalize_snapshot
                result=normalize_snapshot(s.id,policy=read(contained(ROOT/a.policy)) if a.policy else None,activate=a.activate)
            elif a.command=='graph-audit':
                from .knowledge_quality import audit_graph
                result={'snapshot_id':s.id,**audit_graph(s.domain)}
            else:
                from .capabilities import audit_release_dependencies
                review=read(contained(ROOT/a.review)) if a.review else {'snapshot_id':s.id,'decisions':[]}
                if review.get('snapshot_id')!=s.id:raise ValidationError('REVIEW_SNAPSHOT_MISMATCH')
                approved={r['id'] for r in review.get('decisions',[]) if r.get('action')=='approve' and r.get('actor')=='local_user' and str(r.get('reason','')).strip()}
                result={'snapshot_id':s.id,'human_approved_count':len(approved),**audit_release_dependencies(s.domain,approved)}
                if not approved:result.update(status='PENDING_HUMAN',reason='NO_HUMAN_APPROVALS')
            if a.output:write(contained(ROOT/a.output),result)
        elif a.command=='evaluate':
            from .evaluation import evaluate
            result=evaluate(a.suite,read(contained(ROOT/a.config)),online=a.online)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 2 if result.get('status') in ('PARTIAL','FAIL','BLOCKED','PENDING_HUMAN') else 0
    except (ValueError,KeyError,OSError) as e:
        print(json.dumps({'status':'FAIL','error':str(e)},ensure_ascii=False),file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
