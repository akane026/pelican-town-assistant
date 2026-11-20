from __future__ import annotations
from collections import Counter
import copy, re
from .core import *
from .parsing import parse_page,extract_structural,entity_id
from .visual import extract_visual,align_graph

TEXT_PROMPT='''Extract only source-supported candidate entities and directed relations from the supplied paragraphs. Return {entities:[{name,type}],relations:[{subject,predicate,object,quote,block_id,conditions}],facts:[{subject,predicate,value,unit,quote,block_id,conditions}]}. Every quote must be an exact substring of the cited text block. Preserve negation and conditions. Use no outside knowledge. Empty lists are valid. Do not invent rules or executable formulas. All output is unreviewed.'''

def enrich_text(g,bundle,model):
    blocks=bundle['text_blocks'][:6]
    r=model.structured(TEXT_PROMPT,context=blocks,label='v3_text_graph')
    log={'response_status':r.get('status'),'cache_key':r.get('cache_key'),'execution_mode':r.get('execution_mode'),'accepted':0,'rejected':[]}
    if r.get('status')!='OK':g['text_model_log']=log;return g
    known={n['name']:n['id'] for n in g['entities']};blockmap={b['id']:b for b in blocks}
    for n in r['parsed'].get('entities',[]):
        name=n.get('name','')
        if not name or not any(name.lower() in b['text'].lower() for b in blocks):continue
        eid=entity_id(name)
        if eid not in {x['id'] for x in g['entities']}:
            g['entities'].append({'id':eid,'name':name,'type':str(n.get('type','Entity')),'aliases':[],'page_ids':[g['page_id']],'method':'llm_candidate'})
        known[name]=eid
    for kind in ('relations','facts'):
        for rec in r['parsed'].get(kind,[]):
            block=blockmap.get(rec.get('block_id'));quote=rec.get('quote','')
            subject=known.get(rec.get('subject')) or (entity_id(rec.get('subject','')) if entity_id(rec.get('subject','')) in {n['id'] for n in g['entities']} else None)
            if not block or not quote or quote not in block['text'] or not subject:log['rejected'].append('BAD_REFERENCE');continue
            ev={'id':ident('evidence',g['source_id'],block['locator'],quote),'source_id':g['source_id'],'page_id':g['page_id'],
                'revision_id':g['source']['revision_id'],'url':g['source'].get('permanent_url',g['source']['url']),
                'raw_path':g['source']['raw_path'],'source_sha256':g['source']['sha256'],'quote':quote,'quote_sha256':digest(quote.encode()),
                'locator':block['locator'],'review_status':'candidate'}
            g['evidence'].append(ev)
            if kind=='relations':
                obj=known.get(rec.get('object'))
                if not obj:log['rejected'].append('BAD_OBJECT');continue
                item=relation(subject,str(rec.get('predicate','RELATED_TO')),obj,[ev['id']],rec.get('conditions') or {},method='llm_candidate')
            else:
                if not rec.get('unit'):log['rejected'].append('MISSING_UNIT');continue
                item={k:rec[k] for k in ('predicate','value','unit')};item.update(subject=subject,conditions=rec.get('conditions') or {},
                    evidence_ids=[ev['id']],review_status='candidate',answer_allowed=False,critical=True,method='llm_candidate')
                item['id']=ident('fact',subject,item['predicate'],item['value'],item['unit'],item['conditions'])
            g[kind].append(item);log['accepted']+=1
    g['text_model_log']=log;return g

def legacy_rules():
    """One-way migration of previously sourced rule candidates, not another runtime database."""
    legacy=read(ROOT/'verification/data/graph_input.json');out={k:[] for k in ('entities','facts','relations','evidence','assets','occurrences','regions','observations','alignments')}
    source_manifest={s['page_id']:s for s in read(DATA/'manifests/sources.json')}
    # Crop values come from the generic parser. Reuse previously audited rule/formula parsing.
    allowed_types={'EquipmentType','Rule','Season','Item'}
    fmap={};nodes={};evs={};rels={}
    legacyfacts=[n['metadata'] for n in legacy['entities'] if n['type']=='Fact']
    for f in legacyfacts:
        if f['predicate'] in ('grows_into','growth_days','season','buy_price','sell_normal','sell_silver','sell_gold','sell_iridium','duration','stage_durations','regrowth','category'):continue
        sub=entity_id(f['subject']);nodes[sub]={'id':sub,'name':f['subject'].replace('_',' '),'type':'RuleSubject','aliases':[],'page_ids':[]}
        ids=[]
        for e in f['evidence']:
            s=source_manifest[e['page_id']];sid=ident('source',s['page_id'],s['revision_id'],s['sha256'])
            ev={**e,'id':ident('evidence',sid,e['location'],e['quote']),'source_id':sid,'raw_path':'verification/'+e['raw_path'],
                'locator':e['location'],'revision_id':s['revision_id'],'quote_sha256':digest(e['quote'].encode()),'review_status':'candidate'}
            evs[ev['id']]=ev;ids.append(ev['id']);nodes[sub]['page_ids'].append(e['page_id'])
        cond={'knowledge_scope':'frozen_wiki','game_version':'unverified'}
        new={'id':ident('fact',sub,f['predicate'],f['value'],f['unit'],cond),'subject':sub,'predicate':f['predicate'],'value':f['value'],'unit':f['unit'],
             'conditions':cond,'evidence_ids':ids,'review_status':'candidate','answer_allowed':False,'critical':True,
             'method':'legacy_source_migration','legacy_ids':[f['id']]}
        fmap[f['id']]=new;out['facts'].append(new)
    for r in legacy['relationships']:
        fid=r.get('metadata',{}).get('fact_id')
        if fid not in fmap or r['type'] in ('HAS_FACT','SUPPORTED_BY'):continue
        for name in (r['source'],r['target']):
            eid=entity_id(name);nodes.setdefault(eid,{'id':eid,'name':name.replace('_',' '),'type':'Item','aliases':[],'page_ids':[]})
        rr=relation(entity_id(r['source']),r['type'],entity_id(r['target']),fmap[fid]['evidence_ids'],method='legacy_source_migration')
        rels[rr['id']]=rr
    out.update(entities=list(nodes.values()),evidence=list(evs.values()),relations=list(rels.values()))
    return out

def merge_graphs(graphs):
    groups=('entities','facts','relations','evidence','assets','occurrences','regions','observations','alignments')
    merged={k:{} for k in groups};conflicts=[]
    for g in graphs:
        for k in groups:
            for value in g.get(k,[]):
                value=copy.deepcopy(value);old=merged[k].get(value['id'])
                if old:
                    if k=='assets' and value.get('url') and value.get('url')!=old.get('url'):
                        old['url_aliases']=list(dict.fromkeys(old.get('url_aliases',[])+[value['url']]))
                    unions={field:sorted(set(old.get(field,[])+value.get(field,[])))
                            for field in ('evidence_ids','page_ids','aliases','legacy_ids','url_aliases') if field in old or field in value}
                    if k=='entities' and old['type'] in ('Item','Entity','RuleSubject') and value['type'] not in ('Item','Entity','RuleSubject'):old.update(value)
                    for field in ('evidence_ids','page_ids','aliases','legacy_ids','url_aliases'):
                        if field in unions:old[field]=unions[field]
                else:merged[k][value['id']]=value
    slots={}
    for f in merged['facts'].values():
        key=digest([f['subject'],f['predicate'],f['conditions']]);slots.setdefault(key,[]).append(f)
    for slot,values in slots.items():
        if len({canonical([f['value'],f['unit']]) for f in values})>1:
            conflicts.append({'id':ident('conflict',slot),'fact_ids':[f['id'] for f in values],'status':'needs_review'})
            for f in values:f.update(review_status='conflicted',answer_allowed=False)
    result={k:list(v.values()) for k,v in merged.items()};result['conflicts']=conflicts
    validate_graph(result)
    return result

def derive_graph(graphs):
    """Recompute derived knowledge from retained source contributions, never old joins."""
    clean=copy.deepcopy(graphs)
    for graph in clean:
        graph['relations']=[r for r in graph.get('relations',[]) if r.get('method')!='source_grounded_category_join']
        graph['alignments']=[r for r in graph.get('alignments',[]) if r.get('method')!='stage_sequence_illustration/v1']
    fused=merge_graphs(clean)
    # General category/formula join, with both source facts retained as evidence.
    for category in [f for f in fused['facts'] if f['predicate']=='category']:
        for formula in [f for f in fused['facts'] if f['predicate']=='value_formula']:
            evs={e['id']:e for e in fused['evidence']}
            # Evidence ordering must not change semantic applicability. Collect
            # exclusively stated input classes across all supporting quotes;
            # mixed-only or contradictory classes require review, never a join.
            explicit_categories=set()
            for eid in formula['evidence_ids']:
                quote=evs[eid]['quote'].lower()
                fruit=bool(re.search(r'\bfruits?\b',quote));vegetable=bool(re.search(r'\bvegetables?\b',quote))
                if fruit and not vegetable:explicit_categories.add('fruit')
                if vegetable and not fruit:explicit_categories.add('vegetable')
            value=category['value']
            if explicit_categories=={value}:
                r=relation(category['subject'],'CAN_PROCESS',formula['subject'],list(dict.fromkeys(category['evidence_ids']+formula['evidence_ids'])),
                           {'derivation':'category_plus_explicit_formula_input'},method='source_grounded_category_join',support_fact_ids=[category['id'],formula['id']],dependency_contract='v1')
                if r['id'] not in {x['id'] for x in fused['relations']}:fused['relations'].append(r)
    states={}
    for a in fused['alignments']:
        if a['target_kind']=='state' and a['status']=='matched':states.setdefault(a['target_id'],[]).append(a)
    additions=[]
    for r in fused['relations']:
        if r['predicate']!='NEXT_STAGE':continue
        for left in states.get(r['subject'],[]):
            right=next((x for x in states.get(r['object'],[]) if x['page_id']==left['page_id']),None)
            if not right:continue
            additions.append({'id':ident('alignment',r['id'],left['id'],right['id'],'sequence-illustration/v1'),
                'page_id':left['page_id'],'occurrence_id':left['occurrence_id'],'support_occurrence_ids':[left['occurrence_id'],right['occurrence_id']],
                'region_ids':list(dict.fromkeys(left['region_ids']+right['region_ids'])),'target_kind':'relation','target_id':r['id'],
                'evidence_ids':r['evidence_ids'],'evidence_role':'relation_illustration','support_modes':['explicit_stage_headers','pixels'],
                'observation_id':left['observation_id'],'method':'stage_sequence_illustration/v1','status':'matched','review_status':'candidate',
                'confirmation_level':'structural_illustration','support_alignment_ids':[left['id'],right['id']],
                'support_relation_ids':[r['id']],
                'dependency_contract':'v1',
                'answer_allowed':False,'reason_summary':'Explicit stage headers establish sequence; original stage images illustrate appearance only. No day count inferred from pixels.'})
    fused['alignments']+=additions;validate_graph(fused)
    return fused


def reconcile_sources(previous_documents, updates, removed_pages=()):
    """Replace complete per-page contributions, then rebuild joins from surviving inputs.

    Inputs are source document graphs with page_id/source_id, not merged snapshots.
    An update must include the entire current page graph. No approval is inherited
    by changed records. The caller persists returned documents as the next manifest.
    """
    def indexed(documents):
        result={}
        for document in documents:
            document=copy.deepcopy(document);duplicates={}
            for group in ('entities','facts','relations','evidence','assets','occurrences','regions','observations','alignments'):
                seen={}
                for row in document.get(group,[]):
                    if row['id'] in seen:
                        union_fields={'evidence_ids','page_ids','aliases','legacy_ids','url_aliases'}
                        if {k:v for k,v in row.items() if k not in union_fields}!={k:v for k,v in seen[row['id']].items() if k not in union_fields}:
                            raise ValidationError('SOURCE_RECORD_ID_COLLISION:'+row['id'])
                        duplicates[group]=duplicates.get(group,0)+1
                    else:seen[row['id']]=row
            if duplicates:
                document={**document,**merge_graphs([document]),'canonicalization':{'method':'identical_record_dedup_and_reference_union','duplicate_counts':duplicates}}
            page=document.get('page_id')
            if not page or not document.get('source_id'):raise ValidationError('SOURCE_DOCUMENT_ID_REQUIRED')
            if page in result:raise ValidationError('DUPLICATE_SOURCE_DOCUMENT:'+page)
            for evidence in document.get('evidence',[]):
                if evidence.get('page_id',page)!=page or evidence.get('source_id',document['source_id'])!=document['source_id']:
                    raise ValidationError('SOURCE_DOCUMENT_CONTRIBUTION_MISMATCH:'+page)
            validate_graph(document);result[page]=copy.deepcopy(document)
        return result
    before=indexed(previous_documents);replacement=indexed(updates);removed=set(removed_pages)
    if removed & set(replacement):raise ValidationError('SOURCE_UPDATE_DELETE_CONFLICT')
    if removed-set(before):raise ValidationError('UNKNOWN_SOURCE_DELETE')
    after={page:doc for page,doc in before.items() if page not in removed}
    for page,document in replacement.items():
        if page in before and before[page]['source_id']==document['source_id'] and digest(before[page])!=digest(document):
            # A model re-extraction may change graph contributions under an unchanged
            # source ID; the graph revision still invalidates approvals below.
            pass
        for group in ('facts','relations','alignments'):
            for row in document.get(group,[]):
                if row.get('review_status')!='conflicted':row['review_status']='candidate'
                row['answer_allowed']=False;row.pop('approval',None)
        after[page]=document
    prior=derive_graph(list(before.values()));current=derive_graph(list(after.values()))
    prior_records={r['id']:r for k in ('entities','facts','relations','evidence','assets','occurrences','regions','observations','alignments') for r in prior[k]}
    current_records={r['id']:r for k in ('entities','facts','relations','evidence','assets','occurrences','regions','observations','alignments') for r in current[k]}
    for group in ('facts','relations','alignments'):
        for row in current[group]:
            if prior_records.get(row['id'])!=row:
                if row.get('review_status')!='conflicted':row['review_status']='candidate'
                row['answer_allowed']=False;row.pop('approval',None)
    changes={'removed_pages':sorted(removed),'added_pages':sorted(set(replacement)-set(before)),
             'replaced_pages':sorted(set(replacement)&set(before)),
             'source_revisions':[{'page_id':p,'before':before.get(p,{}).get('source_id'),'after':after.get(p,{}).get('source_id')} for p in sorted(set(replacement)|removed)],
             'withdrawn_record_ids':sorted(set(prior_records)-set(current_records)),
             'added_record_ids':sorted(set(current_records)-set(prior_records)),
             'changed_record_ids':sorted(i for i in prior_records.keys()&current_records.keys() if prior_records[i]!=current_records[i]),
             'before_hash':digest(prior),'after_hash':digest(current)}
    return {'documents':[after[p] for p in sorted(after)],'graph':current,'changes':changes}


def integrate_source_contributions(base_domain, previous_documents, updates, removed_pages=()):
    """Actual incremental entry for replaceable documents over an immutable aggregate.

    The aggregate is an explicitly limited layer, never a fabricated per-page
    extraction. Callers can replace it with recovered original contributions once
    their exact lineage has been verified. All joins are recomputed from retained
    records; derived IDs are not accepted as independent source evidence.
    """
    base_pages={e.get('page_id') for e in base_domain.get('evidence',[]) if e.get('page_id')}
    requested={d.get('page_id') for d in updates}|set(removed_pages)
    if base_pages & requested:raise ValidationError('AGGREGATE_SOURCE_REQUIRES_ORIGINAL_CONTRIBUTION:'+','.join(sorted(base_pages & requested)))
    if base_pages & {d.get('page_id') for d in previous_documents}:raise ValidationError('SOURCE_LAYER_OVERLAP')
    result=reconcile_sources(previous_documents,updates,removed_pages)
    result['graph']=derive_graph([base_domain,*result['documents']])
    result['source_layers']={'aggregate_page_ids':sorted(base_pages),'replaceable_page_ids':[d['page_id'] for d in result['documents']],
        'limitation':'Aggregate pages cannot yet be individually replaced through this registry; original contributions are required.'}
    return result


def reconcile_contribution_registry(previous_documents, updates, removed_pages=(), components=()):
    """Rebuild a fully sourced registry and retract stale cross-page components.

    Components carry their original extraction graph plus exact source bindings.
    A source revision change/removal invalidates that component, without turning
    aggregate snapshot slices into fabricated page extraction documents.
    """
    result=reconcile_sources(previous_documents,updates,removed_pages)
    current={d['page_id']:d['source_id'] for d in result['documents']};active=[];component_status=[]
    for component in components:
        graph=component['graph'];validate_graph(graph)
        bindings={(b['page_id'],b['source_id']) for b in component['source_bindings']}
        actual={(e['page_id'],e['source_id']) for e in graph['evidence']}
        if bindings!=actual:raise ValidationError('COMPONENT_SOURCE_BINDING_MISMATCH:'+component['id'])
        stale=[{'page_id':page,'required_source_id':sid,'current_source_id':current.get(page)} for page,sid in sorted(bindings) if current.get(page)!=sid]
        component_status.append({'id':component['id'],'status':'WITHDRAWN_STALE_SOURCE' if stale else 'ACTIVE','stale_bindings':stale})
        if not stale:active.append(graph)
    result['graph']=derive_graph([*result['documents'],*active]);result['component_status']=component_status
    result['source_layers']={'aggregate_page_ids':[],'replaceable_page_ids':sorted(current),
        'limitation':'A legacy component is withdrawn when any original source binding changes; its new revision needs re-extraction before reuse.'}
    return result


def assemble(build_ids):
    """Merge immutable batch outputs and recompute auditable derived records."""
    fused=derive_graph([read(ARTIFACTS/'builds'/bid/'fused_graph.json') for bid in build_ids])
    bid='assembled-'+digest({'inputs':build_ids,'graph':fused})[:16];d=ARTIFACTS/'builds'/bid
    write(d/'fused_graph.json',fused);write(d/'manifest.json',{'build_id':bid,'input_builds':build_ids,'status':'CANDIDATE_BUILT',
        'counts':{k:len(v) for k,v in fused.items()},'post_B_change':'Adds stage sequence illustration; held-out B original output preserved separately.'})
    write(DATA/'latest_build.json',{'build_id':bid,'directory':str(d.relative_to(ROOT))});return bid

def build_batch(batch='baseline',mode='multimodal',online=False,visual_limit=4,text_limit=2,alignment_limit=2,resume=True):
    config=read(ROOT/'configs/corpus.json');sources=read(DATA/'manifests/sources.json');assets=read(DATA/'manifests/assets.json')
    if batch not in ('baseline','all') and batch not in config:raise ValidationError('UNKNOWN_BATCH')
    names=([s['page_id'] for s in sources] if batch=='all' else config[batch]) if batch!='baseline' else config['development']
    selected=[s for s in sources if s['page_id'] in names]
    missing=sorted(set(names)-{s['page_id'] for s in selected})
    # Validate bytes before any checkpoint/cache shortcut. A stale manifest must
    # not make a changed source silently reuse an earlier completed page.
    for source in selected:
        if file_hash(ROOT/source['raw_path'])!=source['sha256']:raise ValidationError('SOURCE_CHANGED:'+source['page_id'])
    for asset in assets:
        if file_hash(ROOT/asset['path'])!=asset['sha256']:raise ValidationError('ASSET_CHANGED:'+asset['id'])
    key=digest({'sources':selected,'assets':assets,'mode':mode,'online':online,'schema':SCHEMA,'code':{p.name:file_hash(p) for p in sorted((ROOT/'stardew_agent').glob('*.py'))},
                'visual_limit':visual_limit,'text_limit':text_limit,'alignment_limit':alignment_limit})
    directory=ARTIFACTS/'builds'/key[:20];directory.mkdir(parents=True,exist_ok=True)
    model=None
    if online:
        from .model import ModelClient
        model=ModelClient()
    aliases=read(ROOT/'configs/aliases.json');graphs=[];processed=[];observation_cache={};all_regions={};visual_calls=0;text_calls=0;alignment_calls=0
    def reuse(cached):
        nonlocal visual_calls,text_calls,alignment_calls
        for o in cached['observations']:
            if o['asset_id'] not in observation_cache:
                rs=[r for r in cached['regions'] if r['asset_id']==o['asset_id']];observation_cache[o['asset_id']]=(o,rs)
                if o['method']=='ChatECNU_visual/v1':visual_calls+=1
        text_calls+=int(bool(cached.get('text_model_log')))
        alignment_calls+=cached.get('model_budget_slots',{}).get('alignment',int(any(a.get('model_call') for a in cached['alignments'])))
    for source in selected:
        page=source['page_id'];pd=directory/'documents'/page;pd.mkdir(parents=True,exist_ok=True)
        checkpoint=pd/'checkpoint.json'
        if resume and checkpoint.exists() and read(checkpoint)['status']=='completed':
            cached=read(pd/'fused_document_graph.json');reuse(cached);graphs.append(cached);processed.append({'page':page,'execution':'checkpoint_reuse'});continue
        write(checkpoint,{'status':'running','at':now()})
        try:
            b=parse_page(source,assets);write(pd/'source_bundle.json',b)
            g=extract_structural(b,assets,aliases)
            page_cache_key=digest({'source':source,'assets':g['assets'],'aliases':aliases,'mode':mode,'online_requested':online,
               'model_ids':{k:model.client.config[k] for k in ('CHATECNU_MODEL','CHATECNU_VISION_MODEL')} if model else None,
               'visual_limit':visual_limit,'text_limit':text_limit,'alignment_limit':alignment_limit,
               'component_hashes':{name:file_hash(ROOT/'stardew_agent'/name) for name in ('parsing.py','visual.py','construction.py','core.py','model.py')}})
            page_cache=DATA/'cache/documents'/(page_cache_key+'.json')
            if resume and page_cache.exists():
                cached=read(page_cache);reuse(cached);graphs.append(cached);write(pd/'fused_document_graph.json',cached)
                write(pd/'text_graph.json',{k:v for k,v in cached.items() if k not in ('observations','regions','alignments')})
                write(pd/'visual_observation.json',cached['observations']);write(pd/'alignment_candidates.json',cached['alignments'])
                write(checkpoint,{'status':'completed','execution':'document_cache_reuse','page_cache_key':page_cache_key})
                processed.append({'page':page,'execution':'document_cache_reuse'});continue
            if model and text_calls<text_limit:
                g=enrich_text(g,b,model);text_calls+=1
            write(pd/'text_graph.json',g)
            observations=[];regions=[]
            occ_asset={o['id']:o.get('asset_id') for o in g['occurrences']}
            anchored_assets={occ_asset[a['occurrence_id']] for a in g['anchors']}
            for asset in g['assets']:
                if asset['id'] not in observation_cache:
                    use_model=model if mode=='multimodal' and visual_calls<visual_limit and asset['id'] in anchored_assets else None
                    o,rs=extract_visual(asset,use_model)
                    if use_model:visual_calls+=1
                    observation_cache[asset['id']]=(o,rs)
                o,rs=observation_cache[asset['id']];observations.append(o);regions.extend(rs)
            g['regions']=regions;g['observations']=observations
            use_align=model if mode=='multimodal' and alignment_calls<alignment_limit else None
            g['alignments']=align_graph(g,observations,regions,use_align)
            g['model_budget_slots']={'alignment':int(bool(use_align))}
            if use_align:alignment_calls+=1
            if mode=='structural':
                for a in g['alignments']:a['method']='structural_only/v1';a['support_modes']=[x for x in a['support_modes'] if x!='pixels'];a['observation_id']=None
                g['observations']=[]
            write(pd/'visual_observation.json',observations if mode=='multimodal' else [])
            write(pd/'alignment_candidates.json',g['alignments']);write(pd/'fused_document_graph.json',g)
            # Failed provider responses are not success caches; deterministic observations remain valid.
            provider_failure=any('model_error' in o for o in observations) or g.get('text_model_log',{}).get('response_status','OK')!='OK' or g.get('alignment_model_log',{}).get('status','OK')!='OK'
            if not provider_failure:write(page_cache,g)
            page_status='partial_provider_failure' if provider_failure else 'completed'
            write(checkpoint,{'status':page_status,'at':now(),'source_sha256':source['sha256']})
            graphs.append(g);processed.append({'page':page,'status':page_status,'facts':len(g['facts']),'alignments':len(g['alignments'])})
            print(page,'completed',len(g['facts']),len(g['alignments']),flush=True)
        except (OSError,ValueError,KeyError) as e:
            write(checkpoint,{'status':'failed','error':str(e),'at':now()});processed.append({'page':page,'status':'failed','error':str(e)})
    graphs.append(legacy_rules())
    fused=merge_graphs(graphs);write(directory/'fused_graph.json',fused)
    manifest={'build_id':directory.name,'mode':mode,'batch':batch,'status':'PARTIAL' if missing or any(p.get('status') in ('failed','partial_provider_failure') for p in processed) else 'CANDIDATE_BUILT',
              'sources':selected,'missing_pages':missing,'pages':processed,'counts':{k:len(v) for k,v in fused.items()},
              'alignment_methods':dict(Counter(a['method'] for a in fused['alignments'])),'model_budget_slots':{'visual':visual_calls,'text':text_calls,'alignment':alignment_calls},
              'review_status':'pending_human','graph_content_hash':digest(fused),'pipeline_key':key}
    write(directory/'manifest.json',manifest);write(DATA/'latest_build.json',{'build_id':directory.name,'directory':str(directory.relative_to(ROOT))})
    return manifest
