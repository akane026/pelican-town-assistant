from __future__ import annotations
import re,time
from collections import defaultdict
from .core import *
from .evidence import BundleStore
from .evidence_payload import graph_payload, chars, BUDGET_DEFINITION_HASH

FACETS={
 'growth_days':['生长','成熟','种植','几天','收获','growth','harvest'], 'season':['季节','春','夏','秋','种植','season'],
 'sell_normal':['售价','卖','价值','收益','普通','price','sale'], 'sell_gold':['金','gold'], 'sell_silver':['银','silver'],
 'value_formula':['加工','果酒','果酱','腌菜','价值','增值','process'], 'materials':['材料','缺','制作','做','craft'],
 'requirements':['献祭','收集包','预留','bundle'], 'choose_k':['献祭','选择','收集包'], 'watered_growth':['浇水','生长','种植'],
 'stage_durations':['阶段','还要','剩余','stage'], 'category':['种类','用途','加工','category'], 'buy_price':['购买','种子','成本'],
 'GROWS_INTO':['种子','种出','seed'], 'CAN_PROCESS':['加工','果酱','果酒','用途'], 'PRODUCED_BY':['设备','加工','小桶'],
 'NEXT_STAGE':['阶段','变化','生长'], 'CONSUMES':['材料','原料','加工'], 'PRODUCES':['产出','加工','用途']}

def tokens(s):
    words=re.findall(r'[a-z0-9_]+|[\u4e00-\u9fff]',s.lower());return set(words)|{a+b for a,b in zip(words,words[1:]) if len(a)==len(b)==1}
def query_terms(query):
    result=tokens(query)
    for field,words in FACETS.items():
        if any(w in query.lower() for w in words):result|=tokens(field)
    return result
def relevance(query,row,entities=()):
    text=' '.join(str(row.get(k,'')) for k in ('name','aliases','predicate','value','conditions','subject','object'))
    words=query_terms(query);score=len(words&tokens(text))/max(1,len(words))
    if row.get('subject') in entities or row.get('object') in entities or row.get('id') in entities:score+=1
    if any(w in query.lower() for w in FACETS.get(row.get('predicate'),[])):score+=1
    return score

def alias_spans(alias,text):
    """Match a literal alias, with word boundaries for ASCII names/IDs."""
    if not isinstance(alias,str) or not alias:return []
    if re.fullmatch(r'[A-Za-z0-9_ :@.-]+',alias):
        pattern=r'(?<![A-Za-z0-9_])'+re.escape(alias)+r'(?![A-Za-z0-9_])'
    else:pattern=re.escape(alias)
    return [m.span() for m in re.finditer(pattern,text,re.I)]

def alias_in_text(alias,text):return bool(alias_spans(alias,text))

def identity_alias_catalog(snapshot):
    path=ROOT/'configs/aliases.json';catalog=read(path)
    aliases={}
    for eid,node in snapshot.records['entities'].items():
        values=node.get('aliases',[])+catalog.get(eid.split(':',1)[-1],[])+[node['name'],eid,eid.split(':',1)[-1].replace('_',' ')]
        aliases[eid]=list(dict.fromkeys(v for v in values if isinstance(v,str) and v))
    return aliases,file_hash(path)

def unique_identity_mention(entity_id,quote,catalog):
    """Authoritative matching inspects all aliases, never the display top-k."""
    own=[span for alias in catalog.get(entity_id,[]) for span in alias_spans(alias,quote)]
    other=[span for eid,aliases in catalog.items() if eid!=entity_id for alias in aliases for span in alias_spans(alias,quote)]
    # A crop alias inside a longer seed name does not independently mention
    # the crop. A separate crop mention elsewhere in the quote can still bind.
    return any(not any(c<=a and b<=d for c,d in other) for a,b in own)

class Retriever:
    def __init__(self,snapshot):
        self.s=snapshot;self.budgets=read(ROOT/'evaluation/protocols/v3.json')['budgets'];self.bundles=BundleStore()
        self.identity_aliases,self.alias_catalog_sha256=identity_alias_catalog(snapshot)
        self.incoming=defaultdict(list)
        for r in snapshot.domain['relations']:self.incoming[r['object']].append(r)
    def resolve(self,query):
        ranked=[]
        for e in self.s.domain['entities']:
            hits=[a for a in self.identity_aliases[e['id']] if len(a)>1 and alias_in_text(a,query)]
            if hits:ranked.append({'entity_id':e['id'],'name':e['name'],'type':e['type'],'score':max(len(a) for a in hits),
                'matched_aliases':hits,'alias_catalog_sha256':self.alias_catalog_sha256})
        return sorted(ranked,key=lambda x:(-x['score'],x['entity_id']))[:5]
    def retrieve(self,query,*,entity_ids=(),conditions=None,task_id='diagnostic',revision=0,method='D',candidate=False,query_regions=(),rerank_model=None):
        if method not in ('A','A+','B','BQ','C','D'):raise ValidationError('UNKNOWN_RETRIEVAL_METHOD')
        start=time.perf_counter();conditions=conditions or {};seeds=list(entity_ids)
        if not seeds:seeds=[r['entity_id'] for r in self.resolve(query)[:3]]
        if any(e not in self.s.records['entities'] for e in seeds):raise ValidationError('UNKNOWN_ENTITY')
        budget=self.budgets;page_scores=defaultdict(float);access={'index_records_scored':0,'edge_reads':0,'node_visits':0,'candidate_records':0,'outside_page_edges':0}
        all_rows=self.s.domain['facts']+self.s.domain['relations']
        base_scores={}
        for r in all_rows:
            access['index_records_scored']+=1;score=relevance(query,r,seeds if method!='A' else ())
            base_scores[r['id']]=score
            for eid in r['evidence_ids']:
                p=self.s.records['evidence'][eid]['page_id'];page_scores[p]=max(page_scores[p],score)
        pages=sorted(page_scores,key=lambda p:(-page_scores[p],p))[:budget['pages']]
        page_phase=time.perf_counter()-start
        pool=[r for r in all_rows if any(self.s.records['evidence'][eid]['page_id'] in pages for eid in r['evidence_ids'])]
        nodes=set(seeds);distance={n:0 for n in nodes};traversed=[]
        if method in ('C','D'):
            queue=[(n,0) for n in seeds]
            while queue and access['edge_reads']<budget['edge_reads'] and len(nodes)<budget['candidate_entities']:
                current,depth=queue.pop(0);access['node_visits']+=1
                if depth>=budget['hops']:continue
                # Inverse lookup is explicit; stored relation direction is never changed.
                for r,direction in [(r,'forward') for r in self.s.adj.get(current,[])]+[(r,'inverse_lookup') for r in self.incoming[current]]:
                    if access['edge_reads']>=budget['edge_reads']:break
                    access['edge_reads']+=1
                    if not any(self.s.records['evidence'][e]['page_id'] in pages for e in r['evidence_ids']):access['outside_page_edges']+=1;continue
                    target=r['object'] if direction=='forward' else r['subject']
                    traversed.append({'relation_id':r['id'],'lookup_direction':direction,'depth':depth+1})
                    if target not in nodes and len(nodes)<budget['candidate_entities']:nodes.add(target);distance[target]=depth+1;queue.append((target,depth+1))
            pool=[r for r in pool if r['subject'] in nodes or r.get('object') in nodes]
            pool.sort(key=lambda r:(distance.get(r['subject'],99),-base_scores[r['id']],r['id']))
        else:pool.sort(key=lambda r:(-base_scores[r['id']],r['id']))
        pool=pool[:60];access['candidate_records']=len(pool)
        # BQ and D share exactly this generic reranker. No graph-path feature is passed.
        rank_trace=None
        if method in ('BQ','D'):
            pool=sorted(pool,key=lambda r:(-relevance(query,r,seeds),r['id']))
            from .reranking import rerank
            pool,rank_trace=rerank(self.s,pool,query,conditions,seeds,query_regions,rerank_model,image_budget=budget['images'])
        trace={'trace_id':ident('retrieval',self.s.id,query,seeds,conditions,method,time.time_ns()),'method':method,'query':query,
               'snapshot_id':self.s.id,'entity_inputs':seeds,'pages':pages,'candidate_ids':[r['id'] for r in pool],
               'selected_ids':[],'traversed':traversed,'budget_used':{},
               'timings':{'page_recall_seconds':page_phase,'total_seconds':time.perf_counter()-start},'execution_mode':'deterministic',
               'reranker':rank_trace['method'] if rank_trace else None,'rerank_trace':rank_trace,
               'limitations':['No learned QM.','Unreviewed visual mappings and identity ambiguity are retained.','Initial evidence may lack rule dependencies.']}
        selected=[];alignment_ids=[];rejected=[]
        def preview(chosen,alignments):
            facts=[r['id'] for r in chosen if r['id'] in self.s.records['facts']]
            rels=[r['id'] for r in chosen if r['id'] in self.s.records['relations']]
            return self.bundles.prepare(self.s,facts,rels,seeds,task_id=task_id,revision=revision,trace=trace,candidate=candidate,alignment_ids=alignments)
        for row in pool:
            if len(selected)>=budget['final_records']:break
            if conditions.get('quality') and row.get('conditions',{}).get('quality') not in (None,conditions['quality']):continue
            proposal=preview(selected+[row],alignment_ids)
            if chars(graph_payload(proposal,trace))>budget['unicode_chars']:
                rejected.append(row['id']);continue
            selected.append(row)
        # Optional visual provenance must fit the same visible budget, including
        # its complete source quotations. It cannot silently expand the bundle.
        body=preview(selected,alignment_ids)
        targets={r['id'] for r in body['facts']+body['relations']+body['entities']}
        for alignment in self.s.domain['alignments']:
            if alignment['target_id'] not in targets or alignment['status']!='matched':continue
            if not candidate and (not alignment.get('answer_allowed') or alignment.get('review_status')!='approved_human'):continue
            proposal=preview(selected,alignment_ids+[alignment['id']])
            if len(proposal['assets'])<=budget['images'] and chars(graph_payload(proposal,trace))<=budget['unicode_chars']:
                alignment_ids.append(alignment['id']);body=proposal
            if len(alignment_ids)>=20:break
        visible_chars=chars(graph_payload(body,trace))
        if visible_chars>budget['unicode_chars']:raise ValidationError('MODEL_EVIDENCE_ENVELOPE_EXCEEDS_BUDGET')
        trace['selected_ids']=[r['id'] for r in selected]
        trace['budget_rejected_record_ids']=rejected
        trace['budget_definition_hash']=BUDGET_DEFINITION_HASH
        trace['budget_used']={**access,'final_records':len(selected),'unicode_chars':visible_chars,
                             'selected_record_unicode_chars':sum(chars(r) for r in selected),'images':len(body['assets'])}
        if rank_trace:
            trace['execution_mode']=rank_trace['execution_mode'];trace['budget_used'].update(rerank_images=rank_trace.get('image_count',0),rerank_model_requests=rank_trace['model_requests'])
        trace['model_visibility']=visibility(body,visible_chars,initial_chars=visible_chars)
        trace['timings']['total_seconds']=time.perf_counter()-start
        facts=[r['id'] for r in selected if r['id'] in self.s.records['facts']];rels=[r['id'] for r in selected if r['id'] in self.s.records['relations']]
        bundle=self.bundles.create(self.s,facts,rels,seeds,task_id=task_id,revision=revision,trace=trace,candidate=candidate,alignment_ids=alignment_ids)
        b=bundle.data()
        payload=graph_payload(b,trace)
        assert chars(payload)==visible_chars
        receipt={'budget_definition_hash':BUDGET_DEFINITION_HASH,'model_visible_evidence_chars':visible_chars,
                 'initial_model_visible_evidence_chars':visible_chars,'cumulative_model_visible_evidence_chars':visible_chars,
                 'full_bundle_unicode_chars':chars(b),'raw_trace_unicode_chars':chars(trace),'phase':'initial'}
        write(ARTIFACTS/'retrieval'/(trace['trace_id'].split(':')[1]+'.json'),{**trace,'audit_schema':'retrieval-audit/v3.2','budget_receipt':receipt,'model_payload':payload,'bundle_id':b['bundle_id']})
        return {'bundle_id':b['bundle_id'],'snapshot_id':self.s.id,'status':'CANDIDATE_EVIDENCE' if candidate else 'EVIDENCE',
             'entities':b['entities'],'relations':b['relations'],'facts':b['facts'],'task_subgraph':b['selected_subgraph'],
             'image_evidence':b['assets'],'evidence_refs':b['evidence_refs'],'trace':trace,'model_payload':payload,'budget_receipt':receipt}

    def supplement(self,bundle,selectors,*,candidate=False,payload_context=None):
        from .rules import matches_selector,missing_dependencies
        b=bundle.data();start=time.perf_counter();facts={f['id'] for f in b['facts']};rels={r['id'] for r in b['relations']};reads=0
        payload_context=payload_context or {}
        existing=facts|rels;pending={}
        for sel in selectors:
            group=self.s.domain['facts'] if sel['kind']=='fact' else self.s.domain['relations']
            for r in group:
                reads+=1
                if matches_selector(r,sel) and r['id'] not in existing:pending[r['id']]=r
        trace={'trace_id':ident('supplement',b['bundle_id'],selectors,time.time_ns()),'operation':'fetch_dependencies','selectors':selectors,
               'records_examined':reads,'missing_dependencies':[],'total_seconds':0,'explicit':True,
               'budget_definition_hash':BUDGET_DEFINITION_HASH,'parent_bundle_id':b['bundle_id']}
        previous=b['retrieval_trace'].get('model_visibility',{})
        seen={key:previous.get(key,[]) for key in ('seen_records','seen_evidence','seen_entities','seen_assets')}
        alignment_ids=[a['id'] for a in b['alignments']]
        def preview(fact_ids,relation_ids):
            return self.bundles.prepare(self.s,fact_ids,relation_ids,[n['id'] for n in b['entities']],task_id=b['task_id'],revision=b['task_revision'],trace=trace,
                supplements=b['explicit_supplement_refs']+[trace['trace_id']],candidate=candidate,alignment_ids=alignment_ids,initial_retrieval_refs=b['initial_retrieval_refs'])
        rejected=[];added=[]
        for rid,row in pending.items():
            proposed_facts=facts|({rid} if rid in self.s.records['facts'] else set())
            proposed_rels=rels|({rid} if rid in self.s.records['relations'] else set())
            proposal=preview(proposed_facts,proposed_rels)
            # Reserve space for terminal progress metadata, which is visible too.
            if chars({**graph_payload(proposal,trace,phase='supplement',**seen),**payload_context})>self.budgets['unicode_chars']-256:
                rejected.append(rid);continue
            facts,rels=proposed_facts,proposed_rels;added.append(rid)
        body=preview(facts,rels);missing=missing_dependencies(body,selectors)
        status='BLOCKED' if pending and not added else 'INCOMPLETE_EVIDENCE' if missing else 'EVIDENCE_SUPPLEMENTED'
        def supplement_payload(value):
            return {**graph_payload(value,trace,phase='supplement',**seen),**payload_context,'supplement_status':status,
                    'missing_dependency_count':len(missing),'reason':'SUPPLEMENT_EVIDENCE_BUDGET_NO_PROGRESS' if status=='BLOCKED' else None}
        payload=supplement_payload(body);visible_chars=chars(payload)
        if visible_chars>self.budgets['unicode_chars']:raise ValidationError('MODEL_EVIDENCE_ENVELOPE_EXCEEDS_BUDGET')
        trace.update(added_ids=added,selected_ids=sorted(facts|rels),budget_rejected_record_ids=rejected,missing_dependencies=missing,
            total_seconds=time.perf_counter()-start,budget_used={'unicode_chars':visible_chars,'added_records':len(added)})
        cumulative=previous.get('cumulative_model_visible_chars',0)+visible_chars
        trace['model_visibility']=visibility(body,cumulative,initial_chars=previous.get('initial_model_visible_chars',0))
        new=self.bundles.create(self.s,facts,rels,[n['id'] for n in b['entities']],task_id=b['task_id'],revision=b['task_revision'],
            trace=trace,supplements=b['explicit_supplement_refs']+[trace['trace_id']],candidate=candidate,alignment_ids=alignment_ids,initial_retrieval_refs=b['initial_retrieval_refs'])
        out=new.data();payload=supplement_payload(out)
        assert chars(payload)==visible_chars
        receipt={'budget_definition_hash':BUDGET_DEFINITION_HASH,'model_visible_evidence_chars':visible_chars,
                 'initial_model_visible_evidence_chars':previous.get('initial_model_visible_chars',0),
                 'cumulative_model_visible_evidence_chars':cumulative,'full_bundle_unicode_chars':chars(out),
                 'raw_trace_unicode_chars':chars(trace),'phase':'supplement'}
        write(ARTIFACTS/'retrieval'/(trace['trace_id'].split(':')[1]+'.json'),{**trace,'audit_schema':'retrieval-audit/v3.2','budget_receipt':receipt,'model_payload':payload,'bundle_id':out['bundle_id']})
        return {'bundle_id':out['bundle_id'],'status':status,'reason':'SUPPLEMENT_EVIDENCE_BUDGET_NO_PROGRESS' if status=='BLOCKED' else None,
                'missing_dependencies':missing,'trace':trace,'facts':out['facts'],'relations':out['relations'],
                'evidence_refs':out['evidence_refs'],'model_payload':payload,'budget_receipt':receipt,**payload_context}


def visibility(body,cumulative_chars,*,initial_chars):
    return {'seen_records':sorted(r['id'] for r in body['facts']+body['relations']),
            'seen_evidence':sorted(r['id'] for r in body['evidence_refs']),
            'seen_entities':sorted(r['id'] for r in body['entities']), 'seen_assets':sorted(r['id'] for r in body['assets']),
            'cumulative_model_visible_chars':cumulative_chars,'initial_model_visible_chars':initial_chars,
            'budget_definition_hash':BUDGET_DEFINITION_HASH}
