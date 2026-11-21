"""Loopback-only workbench. Browser writes require same-origin and a session token."""
from __future__ import annotations
import base64,json,mimetypes,secrets,threading,traceback
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs
from .core import *
from .knowledge import Snapshot,review_export,publish
from .state import TaskStore
from .agent import Agent
from .online_vision import ImageStore,VisualMatcher
from .retrieval import Retriever
from .rules import RULES,rule_audit,record_rule_review,rule_fingerprint,dependencies

class Workbench:
    def __init__(self):
        self.token=secrets.token_urlsafe(32);self.tasks=TaskStore();self.images=ImageStore();self.jobs={};self.lock=threading.Lock()
    def snapshot(self):return Snapshot(allow_candidate=True)
    def reviews(self,s):
        p=DATA/'reviews'/(s.id+'.json')
        return read(p) if p.exists() else {'snapshot_id':s.id,'decisions':[]}
    def task_snapshot(self,t):return Snapshot(t['snapshot_id'],allow_candidate=t['execution_mode']!='released')
    def chat(self,task_id,message):
        if not isinstance(message,str) or not message.strip() or len(message)>12000:raise ValidationError('MESSAGE_LIMIT')
        self.tasks.get(task_id)
        with self.lock:
            if task_id in self.jobs and self.jobs[task_id].is_alive():raise ValidationError('TASK_BUSY')
            def run():
                try:Agent(self.tasks).run(task_id,message)
                except Exception as exc:
                    t=self.tasks.get(task_id)
                    if t['status']!='CANCELLED':self.tasks.save_runtime(task_id,t['revision'],status='ERROR',answer={'status':'ERROR','answer_text':'请求中断，已保存此前工具结果。','error_code':type(exc).__name__})
                    write(ARTIFACTS/'server_errors'/(task_id+'.json'),{'type':type(exc).__name__,'traceback':traceback.format_exc()})
            job=threading.Thread(target=run,daemon=True);self.jobs[task_id]=job;job.start()
        return {'status':'ACCEPTED','task_id':task_id}
    def get(self,path,q):
        if path=='/api/bootstrap':
            try:
                manifest=self.snapshot().manifest
            except ValidationError as exc:
                if str(exc)!='NO_RELEASED_SNAPSHOT':raise
                manifest=None
            return {'csrf':self.token,'snapshot':manifest,'released':read(DATA/'current.json') if (DATA/'current.json').exists() else None,
                    'knowledge_status':'AVAILABLE' if manifest else 'MISSING',
                    'tasks':self.tasks.list(),'rules':[{**r,'audit':rule_audit(k)} for k,r in RULES.items()],
                    'execution_modes':['candidate_diagnostic','released'],'server':'loopback-only'}
        if path=='/api/evaluations':
            return {p.stem:read(p) for p in (ARTIFACTS/'evaluation').glob('*summary.json')}
        s=self.task_snapshot(self.tasks.get(q['task_id'])) if q.get('task_id') else self.snapshot()
        if path=='/api/task':
            t=self.tasks.get(q['id']);return {'task':t,'messages':self.tasks.messages(q['id']),'events':self.tasks.events(q['id']),
                    'running':q['id'] in self.jobs and self.jobs[q['id']].is_alive()}
        if path=='/api/capabilities':
            from .capabilities import assess_capabilities
            t=self.tasks.get(q['task_id']);params=t['inputs'];specs=[]
            for rid,rule in RULES.items():
                dep=dependencies(rid,params,s.domain)
                requirements=[{'input':key} for key in rule['inputs']]+[{'rule':{'id':rid,'fingerprint':rule_fingerprint(rid)}}]
                requirements += [{'selector':selector} for selector in dep['selectors']]
                if dep.get('dependency_discovery_incomplete'):requirements.append({'input':'resolved_growth_target'})
                specs.append({'id':rid,'description':rule['description'],'dependencies':{'all':requirements}})
            return assess_capabilities(s.domain,specs,rule_reviews={rid:rule_audit(rid) for rid in RULES},params=params,snapshot_id=s.id,task_revision=t['revision'])
        if path=='/api/search':return {'entities':Retriever(s).resolve(q.get('q',''))}
        if path=='/api/graph':
            eid=q.get('id');rels=[r for r in s.domain['relations'] if not eid or eid in (r['subject'],r['object'])][:45]
            ids={x for r in rels for x in (r['subject'],r['object'])}
            if eid in s.records['entities']:ids.add(eid)
            return {'nodes':[s.records['entities'][x] for x in ids],'edges':rels,'snapshot_id':s.id,'truncated':len(rels)==45}
        if path=='/api/record':
            rid=q['id'];record=next((s.records[k][rid] for k in s.records if rid in s.records[k]),None)
            if not record:raise ValidationError('UNKNOWN_RECORD')
            aligns=[a for a in s.domain['alignments'] if a['target_id']==rid or a['id']==rid]
            region_ids={i for a in aligns for i in a['region_ids']}
            regions=[s.records['regions'][i] for i in region_ids]
            assets=[s.records['assets'][i] for i in {r['asset_id'] for r in regions}]
            obsids={a['observation_id'] for a in aligns if a.get('observation_id')}
            return {'snapshot_id':s.id,'record':record,'evidence':[s.records['evidence'][i] for i in record.get('evidence_ids',[])],
                    'alignments':aligns,'regions':regions,'assets':assets,'observations':[s.records['observations'][i] for i in obsids]}
        if path=='/api/review':
            decisions={x['id']:x for x in self.reviews(s)['decisions']};kind=q.get('kind','alignments');kind=kind if kind in ('facts','relations','alignments') else 'alignments'
            items=s.domain[kind];needle=q.get('q','').lower();items=[r for r in items if needle in canonical(r).lower()]
            offset=max(0,int(q.get('offset',0)))
            return {'snapshot_id':s.id,'kind':kind,'total':len(items),'offset':offset,'items':[{'record':r,'decision':decisions.get(r['id'])} for r in items[offset:offset+30]],
                    'decisions_count':len(decisions),'quality':read(s.directory/'quality.json')}
        if path=='/api/export':
            tid=q['id'];t=self.tasks.get(tid);content={'task':t,'messages':self.tasks.messages(tid),'events':self.tasks.events(tid)}
            if q.get('format')=='md':
                lines=['# 星露谷助手任务导出','',f'模式：{t["execution_mode"]}',f'快照：{t["snapshot_id"]}',f'任务版本：{t["revision"]}','']
                for m in content['messages']:lines += [f'## {m["role"]}','',m['content'] if isinstance(m['content'],str) else m['content'].get('answer_text',canonical(m['content'])),'']
                lines+=['## 工具与证据记录','','```json',json.dumps(content['events'],ensure_ascii=False,indent=2),'```']
                return '\n'.join(lines)
            return content
        raise ValidationError('ROUTE_NOT_FOUND')
    def post(self,path,d):
        if path=='/api/task':
            mode=d.get('mode','candidate_diagnostic')
            if mode not in ('candidate_diagnostic','released'):raise ValidationError('INVALID_MODE')
            s=Snapshot(allow_candidate=mode!='released');return self.tasks.create(s.id,mode)
        if path=='/api/chat':return self.chat(d['task_id'],d['message'])
        if path=='/api/cancel':
            t=self.tasks.get(d['task_id']);return self.tasks.cancel(t['task_id'],d.get('revision',t['revision']))
        if path=='/api/state':return self.tasks.update(d['task_id'],d['revision'],d['fields'],source='user_ui',quote=d.get('quote','explicit workbench input'))
        if path=='/api/upload':
            t=self.tasks.get(d['task_id']);r=self.images.upload(base64.b64decode(d['data'],validate=True),t['task_id'])
            uploads={x['image_id']:x for x in t['uploaded_images']};uploads[r['image_id']]=r
            self.tasks.save_runtime(t['task_id'],t['revision'],uploaded_images=list(uploads.values()));return r
        if path=='/api/region':
            t=self.tasks.get(d['task_id']);r=self.images.region(d['image_id'],t['task_id'],d['bbox']);regions={x['region_id']:x for x in t['selected_regions']};regions[r['region_id']]=r
            if d.get('replace_region_id'):
                if d['replace_region_id'] not in regions:raise ValidationError('UNKNOWN_REGION')
                del regions[d['replace_region_id']]
            t=self.tasks.invalidate(t['task_id'],d.get('revision',t['revision']),reason='regions_changed',selected_regions=list(regions.values()))
            return {'region':r,'task_revision':t['revision'],'match':VisualMatcher(self.task_snapshot(t)).match(ROOT/r['path'],d.get('kind','item'))}
        if path=='/api/confirm':
            t=self.tasks.get(d['task_id']);s=self.task_snapshot(t)
            if not any(x['region_id']==d['region_id'] for x in t['selected_regions']):raise ValidationError('UNKNOWN_REGION')
            if d.get('entity_id') not in s.records['entities']:raise ValidationError('UNKNOWN_ENTITY_USE_SEARCH')
            confirmed=dict(t['inputs'].get('confirmed_entities',{}));confirmed[d['region_id']]={'entity_id':d['entity_id'],'quantity':d.get('quantity'),'quality':d.get('quality'),'source':'user_confirmation','candidate_override':True}
            return self.tasks.update(t['task_id'],d['revision'],{'confirmed_entities':confirmed},source='user_ui')
        if path=='/api/review':
            s=self.snapshot()
            if d.get('snapshot_id')!=s.id:raise ValidationError('REVIEW_SNAPSHOT_MISMATCH')
            if not any(d['id'] in s.records[k] for k in ('facts','relations','alignments')):raise ValidationError('UNKNOWN_REVIEW_RECORD')
            if d.get('action') not in ('approve','reject','defer') or not str(d.get('reason','')).strip():raise ValidationError('REVIEW_REASON_REQUIRED')
            review=self.reviews(s);record={'id':d['id'],'action':d['action'],'reason':d['reason'],'actor':'local_user','at':now(),'via':'same_origin_workbench'}
            review['decisions']=[x for x in review['decisions'] if x['id']!=record['id']]+[record];write(DATA/'reviews'/(s.id+'.json'),review)
            append(ARTIFACTS/'review/actions.jsonl',{'snapshot_id':s.id,**record});return record
        if path=='/api/publish':
            s=self.snapshot()
            if d.get('snapshot_id')!=s.id:raise ValidationError('REVIEW_SNAPSHOT_MISMATCH')
            return publish(s.id,self.reviews(s))
        if path=='/api/rule-review':return record_rule_review(d['rule_id'],d['action'],d['reason'])
        raise ValidationError('ROUTE_NOT_FOUND')
    def image(self,q):
        if q.get('kind')=='upload':return ROOT/self.images.get(q['id'],q['task_id'])['path']
        s=self.task_snapshot(self.tasks.get(q['task_id'])) if q.get('task_id') else self.snapshot();r=s.records['assets'].get(q.get('id'))
        if not r:raise ValidationError('UNKNOWN_ASSET')
        return contained(ROOT/r['path'])

def make_server(host='127.0.0.1',port=8765):
    if host not in ('127.0.0.1','localhost'):raise ValidationError('LOOPBACK_ONLY')
    app=Workbench()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*a):pass
        def reply(self,status,body,ctype='application/json; charset=utf-8'):
            data=body if isinstance(body,bytes) else (body if isinstance(body,str) else canonical(body)).encode()
            self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' blob: data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers();self.wfile.write(data)
        def safe_host(self):
            return self.headers.get('Host','') in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}')
        def do_GET(self):
            if not self.safe_host():return self.reply(403,{'error':'HOST_DENIED'})
            p=urlparse(self.path);q={k:v[0] for k,v in parse_qs(p.query).items()}
            try:
                if p.path=='/api/image':
                    f=app.image(q);return self.reply(200,f.read_bytes(),mimetypes.guess_type(f.name)[0] or 'image/png')
                if p.path.startswith('/api/'):
                    r=app.get(p.path,q);return self.reply(200,r,'text/markdown; charset=utf-8' if isinstance(r,str) else 'application/json; charset=utf-8')
                if p.path not in ('/','/app.js','/styles.css'):return self.reply(404,{'error':'NOT_FOUND'})
                f=ROOT/'web'/('index.html' if p.path=='/' else p.path[1:]);self.reply(200,f.read_bytes(),mimetypes.guess_type(f.name)[0]+'; charset=utf-8')
            except (ValueError,KeyError,OSError) as exc:self.reply(400,{'error':str(exc)[:250],'type':type(exc).__name__})
        def do_POST(self):
            origin=self.headers.get('Origin');allowed={f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}
            if not self.safe_host() or origin not in allowed or not secrets.compare_digest(self.headers.get('X-CSRF-Token',''),app.token):return self.reply(403,{'error':'ORIGIN_OR_CSRF_DENIED'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=14_000_000:raise ValidationError('REQUEST_LIMIT')
                d=json.loads(self.rfile.read(size))
                if not isinstance(d,dict):raise ValidationError('JSON_OBJECT_REQUIRED')
                self.reply(200,app.post(urlparse(self.path).path,d))
            except (ValueError,KeyError,TypeError,OSError) as exc:self.reply(400,{'error':str(exc)[:250],'type':type(exc).__name__})
    server=ThreadingHTTPServer((host,port),Handler);server.app=app;return server

def serve(host='127.0.0.1',port=8765):
    server=make_server(host,port);print(f'Workbench: http://{host}:{server.server_port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.shutdown();server.server_close()
