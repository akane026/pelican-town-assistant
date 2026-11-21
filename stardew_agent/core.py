from __future__ import annotations
import hashlib, json, os, sqlite3, tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
ARTIFACTS=ROOT/'artifacts/v3'
SCHEMA='stardew/v3.1'
def now():return datetime.now(timezone.utc).isoformat()
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(value):return hashlib.sha256(value if isinstance(value,bytes) else canonical(value).encode()).hexdigest()
def file_hash(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ident(kind,*parts):return kind+':'+digest(parts)[:28]
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(dir=path.parent,prefix=path.name+'.',suffix='.tmp')
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as f:f.write(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n')
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)
def rows(path):return [json.loads(s) for s in Path(path).read_text(encoding='utf-8').splitlines() if s.strip()]
def append(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a',encoding='utf-8',newline='\n') as f:f.write(canonical(value)+'\n')
def contained(path,root=ROOT):
    p=Path(path).resolve();base=Path(root).resolve()
    if not p.is_relative_to(base):raise ValidationError('PATH_NOT_ALLOWED')
    return p
class ValidationError(ValueError):
    pass

def relation(subject,predicate,obj,evidence_ids,conditions=None,**extra):
    conditions=conditions or {}
    return dict(id=ident('relation',subject,predicate,obj,conditions),subject=subject,predicate=predicate,object=obj,
                direction='forward',conditions=conditions,evidence_ids=evidence_ids,review_status='candidate',**extra)

def validate_bbox(box):
    if not isinstance(box,list) or len(box)!=4 or any(type(x) not in (int,float) for x in box):raise ValidationError('INVALID_BBOX')
    x1,y1,x2,y2=box
    if not (0<=x1<x2<=1 and 0<=y1<y2<=1):raise ValidationError('INVALID_BBOX')
    return box

def validate_graph(g):
    groups=('entities','facts','relations','evidence','assets','occurrences','regions','observations','alignments')
    indexes={k:{r['id']:r for r in g.get(k,[])} for k in groups}
    for k in groups:
        if len(indexes[k])!=len(g.get(k,[])):raise ValidationError('DUPLICATE_ID:'+k)
    for r in g.get('relations',[]):
        if r['direction']!='forward' or r['subject'] not in indexes['entities'] or r['object'] not in indexes['entities']:raise ValidationError('RELATION_ENDPOINT')
        if r['id']!=relation(r['subject'],r['predicate'],r['object'],[],r['conditions'])['id']:raise ValidationError('RELATION_ID')
    for f in g.get('facts',[]):
        if f['subject'] not in indexes['entities'] or not f.get('unit'):raise ValidationError('FACT_SUBJECT_OR_UNIT')
    for r in g.get('regions',[]):
        validate_bbox(r['bbox'])
        if r['asset_id'] not in indexes['assets']:raise ValidationError('REGION_ASSET')
    for o in g.get('occurrences',[]):
        if o.get('asset_id') and o['asset_id'] not in indexes['assets']:raise ValidationError('OCCURRENCE_ASSET')
    for a in g.get('alignments',[]):
        group={'entity':'entities','state':'entities','relation':'relations','fact':'facts'}.get(a['target_kind'])
        if not group or a['target_id'] not in indexes[group]:raise ValidationError('ALIGNMENT_TARGET')
        if any(i not in indexes['regions'] for i in a['region_ids']):raise ValidationError('ALIGNMENT_REGION')
        if a.get('occurrence_id') and a['occurrence_id'] not in indexes['occurrences']:raise ValidationError('ALIGNMENT_OCCURRENCE')
        if a.get('observation_id') and a['observation_id'] not in indexes['observations']:raise ValidationError('ALIGNMENT_OBSERVATION')
    for k in ('facts','relations','alignments'):
        for r in g.get(k,[]):
            if not r.get('evidence_ids') or any(e not in indexes['evidence'] for e in r['evidence_ids']):raise ValidationError('MISSING_EVIDENCE:'+r['id'])
    from .knowledge_quality import validate_visual_links
    validate_visual_links(g)
    return indexes

def database(path):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(path,timeout=15)
    con.execute('PRAGMA foreign_keys=ON')
    return con
