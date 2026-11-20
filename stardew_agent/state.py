from __future__ import annotations
import uuid,re
from .core import *

FIELDS={'goal','date','inventory','equipment','bundle_progress','confirmed_entities','quality','profession','quantity','watered','acceleration','season','day','selected_regions','entity_id','product_id','completed','user_level','stage','elapsed_in_stage','plan_option','entity_inputs'}
INPUT_VALUE_WORDS={
    'quality':{'normal':['普通','无星'],'silver':['银星'],'gold':['金星'],'iridium':['铱星']},
    'profession':{'none':['无职业','没有职业','无加成'],'artisan':['工匠'],'tiller':['农耕人','耕种者']},
    'season':{'Spring':['春季','春天'],'Summer':['夏季','夏天'],'Fall':['秋季','秋天'],'Winter':['冬季','冬天']},
    'acceleration':{'none':['无加速','没有加速','不加速']},
    'watered':{True:['每天浇水','每日浇水','一直浇水'],False:['未浇水','没有浇水','没浇水']}}

def check_extracted_values(fields,quote):
    """Lexical provenance guard; this is deliberately not a semantic approval."""
    for key,value in fields.items():
        if key in INPUT_VALUE_WORDS:
            terms=[str(value)]+INPUT_VALUE_WORDS[key].get(value,[])
            shorthand=False
            if key=='season' and value in ('Spring','Summer','Fall','Winter'):
                symbol={'Spring':'春','Summer':'夏','Fall':'秋','Winter':'冬'}[value]
                # A bounded calendar expression, not a lone seasonal character
                # inside a plant name or an unrelated word such as 春卷.
                dates=re.findall(re.escape(symbol)+r'(?:季)?\s*(?:第\s*)?([1-9]|1\d|2[0-8])\s*(?:日|天|号)(?!\d)',quote)
                shorthand=any('day' not in fields or int(d)==fields['day'] for d in dates)
            if not shorthand and not any(term.casefold() in quote.casefold() for term in terms):raise ValidationError('STATE_VALUE_NOT_IN_QUOTE:'+key)
        if key=='entity_inputs' and isinstance(value,dict):
            for scoped in value.values():
                if isinstance(scoped,dict):check_extracted_values(scoped,quote)

def defaults(state):
    for key,value in {'goal_spec':{},'previous_goal_spec':{},'goal_coverage':{},'user_turns':[],'current_turn_id':None,'invalidation_history':[],'visual_results':[]}.items():state.setdefault(key,value)
    return state

def extracted_numbers(value):
    if isinstance(value,bool):return []
    if isinstance(value,(int,float)):return [value]
    if isinstance(value,dict):return [n for v in value.values() for n in extracted_numbers(v)]
    if isinstance(value,list):return [n for v in value for n in extracted_numbers(v)]
    return []

def valid_source_excerpt(quote,text):
    """A literal excerpt may not start/end inside an ASCII/number token."""
    if not isinstance(quote,str) or not quote:return False
    token=lambda c:bool(c and re.fullmatch(r'[A-Za-z0-9_.:\-]',c))
    for match in re.finditer(re.escape(quote),text):
        start,end=match.span()
        if start and token(text[start-1]) and token(quote[0]):continue
        if end<len(text) and token(text[end]) and token(quote[-1]):continue
        return True
    return False

def registered_regions(task):
    """Validate image-store registration before using any user-region path."""
    from .online_vision import ImageStore
    regions=task.get('selected_regions',[])
    if not isinstance(regions,list):raise ValidationError('INVALID_REGISTERED_REGIONS')
    valid={}
    for row in regions:
        if not isinstance(row,dict) or not isinstance(row.get('region_id'),str) or not isinstance(row.get('image_id'),str):raise ValidationError('INVALID_REGISTERED_REGION')
        validate_bbox(row.get('bbox'))
        expected_id=ident('user_region',row['image_id'],row['bbox'],'v1')
        expected_path=DATA/'uploads'/task['task_id']/(expected_id.split(':')[1]+'.png')
        if row['region_id']!=expected_id or row.get('task_id')!=task['task_id'] or row.get('path')!=str(expected_path.relative_to(ROOT)):raise ValidationError('UNREGISTERED_REGION_PATH')
        ImageStore().get(row['image_id'],task['task_id'])
        if file_hash(expected_path)!=row.get('sha256'):raise ValidationError('REGISTERED_REGION_CHANGED')
        valid[row['region_id']]=row
    return valid

def clear_derived(state,reason):
    """One invalidation boundary for inputs, goals, regions, new turns and cancel."""
    state['revision']+=1
    state['stale_result_ids']=list(dict.fromkeys(state.get('stale_result_ids',[])+state.get('results',[])))
    state.update(results=[],visual_results=[],inventory_plan_copy={},goal_coverage={},status='READY')
    for key in ('answer','last_bundle_id','missing_inputs','messages_checkpoint'):state.pop(key,None)
    if state.get('goal_spec'):state['goal_spec']['task_revision']=state['revision']
    state['invalidation_history']=(state.get('invalidation_history',[])+[{'reason':reason,'revision':state['revision'],'at':now()}])[-50:]
    return state

class TaskStore:
    def __init__(self,path=None):
        self.path=Path(path) if path else DATA/'runtime/tasks.sqlite3'
        with database(self.path) as db:
            db.executescript('CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,revision INTEGER,state TEXT); CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,task_id TEXT,revision INTEGER,role TEXT,content TEXT); CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,task_id TEXT,revision INTEGER,event TEXT);')
    def create(self,snapshot_id,mode='candidate_diagnostic'):
        task={'task_id':str(uuid.uuid4()),'revision':0,'snapshot_id':snapshot_id,'execution_mode':mode,'inputs':{},'input_sources':{},
              'inventory_plan_copy':{},'uploaded_images':[],'selected_regions':[],'status':'READY','results':[],'stale_result_ids':[],'created_at':now()}
        defaults(task)
        with database(self.path) as db:db.execute('INSERT INTO tasks VALUES (?,?,?)',(task['task_id'],0,canonical(task)))
        return task
    def get(self,task_id):
        with database(self.path) as db:row=db.execute('SELECT state FROM tasks WHERE id=?',(task_id,)).fetchone()
        if not row:raise ValidationError('TASK_NOT_FOUND')
        return defaults(json.loads(row[0]))
    def list(self):
        with database(self.path) as db:return [defaults(json.loads(r[0])) for r in db.execute('SELECT state FROM tasks ORDER BY rowid DESC LIMIT 100')]
    def _mutate(self,task_id,expected_revision,change):
        with database(self.path) as db:
            db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT revision,state FROM tasks WHERE id=?',(task_id,)).fetchone()
            if not row or row[0]!=expected_revision:raise ValidationError('STALE_TASK_REVISION')
            state=defaults(json.loads(row[1]));change(state)
            db.execute('UPDATE tasks SET revision=?,state=? WHERE id=?',(state['revision'],canonical(state),task_id))
        return state
    def begin_turn(self,task_id,message):
        if not isinstance(message,str) or not message.strip():raise ValidationError('USER_MESSAGE_REQUIRED')
        previous=self.get(task_id)
        def change(state):
            old=state.get('goal_spec',{})
            clear_derived(state,'user_turn')
            state['previous_goal_spec']=old;state['goal_spec']={}
            turn={'turn_id':'turn:'+str(uuid.uuid4()),'text':message,'at':now()}
            state['user_turns'].append(turn);state['current_turn_id']=turn['turn_id']
        state=self._mutate(task_id,previous['revision'],change)
        self.message(task_id,'user',message)
        return state
    def set_goals(self,task_id,expected_revision,spec,source_turn_id=None):
        from .task_contract import normalize_goals
        def change(state):
            if source_turn_id and source_turn_id!=state.get('current_turn_id'):raise ValidationError('STALE_SOURCE_TURN')
            normalized=normalize_goals(spec,state)
            clear_derived(state,'goals_changed');normalized['task_revision']=state['revision'];state['goal_spec']=normalized
        return self._mutate(task_id,expected_revision,change)
    def invalidate(self,task_id,expected_revision,reason,**runtime_fields):
        if set(runtime_fields)-{'selected_regions','uploaded_images'}:raise ValidationError('INVALID_INVALIDATION_FIELD')
        def change(state):
            if 'selected_regions' in runtime_fields:registered_regions({**state,'selected_regions':runtime_fields['selected_regions']})
            clear_derived(state,reason);state.update(runtime_fields)
        return self._mutate(task_id,expected_revision,change)
    def cancel(self,task_id,expected_revision):
        def change(state):
            clear_derived(state,'cancelled');state['status']='CANCELLED'
        return self._mutate(task_id,expected_revision,change)
    def update(self,task_id,expected_revision,fields,*,source='user_ui',quote=''):
        if set(fields)-FIELDS:raise ValidationError('UNKNOWN_STATE_FIELDS')
        if 'selected_regions' in fields:raise ValidationError('REGIONS_REQUIRE_REGISTERED_IMAGE_API')
        if 'confirmed_entities' in fields and source not in ('user_ui','user_confirmation'):raise ValidationError('HUMAN_CONFIRMATION_REQUIRED')
        if source=='user_text_extracted':
            current=self.get(task_id);turns={r['turn_id']:r['text'] for r in current.get('user_turns',[])}
            full=turns.get(current.get('current_turn_id'),quote)
            if not valid_source_excerpt(quote,full):raise ValidationError('STATE_QUOTE_SPLITS_SOURCE_TOKEN')
            check_extracted_values(fields,quote)
        def change(state):
            if 'confirmed_entities' in fields:
                confirmed=fields['confirmed_entities'];regions=registered_regions(state)
                if not isinstance(confirmed,dict):raise ValidationError('INVALID_CONFIRMED_ENTITIES')
                for rid,row in confirmed.items():
                    if not isinstance(rid,str) or rid not in regions or not isinstance(row,dict):raise ValidationError('CONFIRMATION_REGION_REQUIRED')
                    if not isinstance(row.get('entity_id'),str) or not row['entity_id'].startswith('entity:'):raise ValidationError('INVALID_CONFIRMED_ENTITY')
                    if row.get('quantity') is not None and (type(row['quantity'])!=int or row['quantity']<0):raise ValidationError('INVALID_CONFIRMED_QUANTITY')
                    if row.get('quality') is not None and row['quality'] not in ('normal','silver','gold','iridium'):raise ValidationError('INVALID_CONFIRMED_QUALITY')
            clear_derived(state,'inputs_changed')
            for key,value in fields.items():
                if key in ('quantity','day','user_level','stage','elapsed_in_stage','plan_option') and (type(value)!=int or value<0):raise ValidationError('INVALID_STATE_NUMBER')
                if source=='user_text_extracted':
                    # This checks literal numeric provenance, not semantic truth
                    # of an extraction. Chinese number words require clarification
                    # or direct UI confirmation instead of a silent conversion.
                    supplied={float(n) for n in re.findall(r'(?<![A-Za-z0-9_.])\d+(?:\.\d+)?(?![A-Za-z0-9_.])',full)}
                    if any(float(n) not in supplied for n in extracted_numbers(value)):raise ValidationError('STATE_NUMBER_NOT_IN_QUOTE')
                state['inputs'][key]=value;state['input_sources'][key]={'source':source,'quote':quote,'at':now(),'turn_id':state.get('current_turn_id'),'human_confirmation':source in ('user_ui','user_confirmation')}
                if key=='selected_regions':state['selected_regions']=value
        return self._mutate(task_id,expected_revision,change)
    def save_runtime(self,task_id,revision,**fields):
        allowed={'status','results','visual_results','uploaded_images','selected_regions','inventory_plan_copy','missing_inputs','answer','last_bundle_id','messages_checkpoint','goal_coverage'}
        if set(fields)-allowed:raise ValidationError('INVALID_RUNTIME_FIELD')
        with database(self.path) as db:
            db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT revision,state FROM tasks WHERE id=?',(task_id,)).fetchone()
            if not row or row[0]!=revision:raise ValidationError('STALE_TASK_REVISION')
            state=defaults(json.loads(row[1]))
            if state.get('status')=='CANCELLED' and (fields.get('status','CANCELLED')!='CANCELLED' or any(k in fields for k in ('results','visual_results','inventory_plan_copy','last_bundle_id'))):raise ValidationError('TASK_CANCELLED')
            state.update(fields);db.execute('UPDATE tasks SET state=? WHERE id=?',(canonical(state),task_id))
        return state
    def message(self,task_id,role,content):
        s=self.get(task_id)
        with database(self.path) as db:db.execute('INSERT INTO messages(task_id,revision,role,content) VALUES (?,?,?,?)',(task_id,s['revision'],role,canonical(content)))
    def messages(self,task_id):
        with database(self.path) as db:return [{'role':r[0],'content':json.loads(r[1])} for r in db.execute('SELECT role,content FROM messages WHERE task_id=? ORDER BY id',(task_id,))]
    def event(self,task_id,value):
        s=self.get(task_id)
        with database(self.path) as db:db.execute('INSERT INTO events(task_id,revision,event) VALUES (?,?,?)',(task_id,s['revision'],canonical(value)))
    def events(self,task_id):
        with database(self.path) as db:return [json.loads(r[0]) for r in db.execute('SELECT event FROM events WHERE task_id=? ORDER BY id',(task_id,))]
