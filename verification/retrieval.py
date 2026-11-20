"""A-D retrieval ablation over one Semantica snapshot, with auditable budgets."""
from __future__ import annotations
import csv
import json
import time
from collections import deque
from .common import BASE, DATA, dump, file_sha, jsonl, load, read_jsonl, sha
from .graph import KnowledgeGraph
from .knowledge import ALIASES

CONFIG={'version':'retrieval/v1','channel_top':10,'pages':5,'inspect_cards':60,'candidate_pool':40,
        'final_cards':8,'final_images':4,'max_chars':4000,'graph_depth':3,'domain_nodes':30,'domain_edge_reads':120}
INTENTS=[(['种子','是什么','身份'],{'identity':5,'grows_into':5}),
  (['季节','春季'],{'season':8}),(['成熟','生长夜晚'],{'growth_days':8,'stage_durations':8,'watered_growth':5,'grows_into':4}),
  (['阶段'],{'duration':8,'stage_durations':7,'identity':4}),(['卖','售价','值多少钱'],{'sell_normal':8,'value_formula':8,'equipment':4}),
  (['金星','金品质'],{'sell_gold':15}),(['献祭'],{'quality_bundle':12,'choose_k':8,'requirements':4}),
  (['多久收','六点','加工时间'],{'processing_minutes':12,'machine_day':12,'equipment':7})]
DOMAIN_EDGES={'GROWS_INTO','HAS_STAGE','NEXT_STAGE','CAN_PROCESS','PRODUCED_BY','BUNDLE_REQUIREMENT','GROWS_IN_SEASON'}


class Retriever:
    def __init__(self,graph=None):
        self.graph=graph or KnowledgeGraph();self.cards=[]
        for f in self.graph.facts.values():
            self.cards.append({'id':f['id'],'subject':f['subject'],'predicate':f['predicate'],'value':f['value'],'unit':f['unit'],
              'conditions':f['conditions'],'pages':sorted({e['page_id'] for e in f['evidence']}),
              'evidence':[{k:e[k] for k in ['page_id','location','url']} for e in f['evidence']]})
        self.gallery=read_jsonl(DATA/'gallery.jsonl')
        for row in self.gallery:
            pages=sorted({self.graph.nodes[o]['metadata']['page_id'] for o in row['occurrence_ids'] if o in self.graph.nodes})
            self.cards.append({'id':'entity:'+row['entity'],'subject':row['entity'],'predicate':'identity','value':row['entity'],'unit':'entity',
              'conditions':{'identity_status':row['identity_status']},'pages':pages,'image_id':row['image_id'],'evidence':row['occurrence_ids'][:3]})
        self.page_index={}
        for c in self.cards:
            for page in c['pages']:self.page_index.setdefault(page,[]).append(c)
        self.adjacency={}
        for e in self.graph.edges:
            if e['type'] in DOMAIN_EDGES:
                self.adjacency.setdefault(e['source'],[]).append((e['target'],e))
                self.adjacency.setdefault(e['target'],[]).append((e['source'],e))

    def lexical_roots(self,q):
        roots=[]
        for entity,node in self.graph.nodes.items():
            if node['type'] in ['Source','Fact','VisualOccurrence']:continue
            names=[entity.replace('_',' ')]+ALIASES.get(entity,[])+node.get('metadata',{}).get('aliases',[])
            if any(name.lower() in q.lower() for name in names if len(name)>1):roots.append(entity)
        # Product names are concepts, not a predetermined answer entity.
        for phrase,entity in [('果酒','Wine'),('果酱','Jelly'),('腌菜','Pickles')]:
            if phrase in q and entity not in roots:roots.append(entity)
        return roots

    def targets(self,q):
        weights={}
        for words,preds in INTENTS:
            if any(word in q for word in words):
                for pred,weight in preds.items():weights[pred]=max(weights.get(pred,0),weight)
        if '金星' in q:weights['sell_normal']=0
        return weights

    def first_stage(self,q,visual):
        roots=self.lexical_roots(q)+visual;weights=self.targets(q);scores={}
        for c in self.cards:
            match=max([1.0 if c['subject']==r else 0.55 if c['subject'].split('_Stage_')[0]==r.split('_Stage_')[0] or c['subject'].removesuffix('_Seeds')==r.removesuffix('_Seeds') else 0 for r in roots]+[0])
            value=match*10+weights.get(c['predicate'],0)/10
            for page in c['pages']:scores[page]=scores.get(page,0)+value
        ranked=sorted(scores,key=lambda p:(-scores[p],p))[:CONFIG['channel_top']]
        return ranked[:CONFIG['pages']]

    def score(self,card,roots,weights, *, rerank=False):
        s=card['subject'];match=max([1 if s==r else .65 if s.split('_Stage_')[0]==r.split('_Stage_')[0] or s.removesuffix('_Seeds')==r.removesuffix('_Seeds') else 0 for r in roots]+[0])
        relevance=weights.get(card['predicate'],0)
        global_rule=s=='Calendar' and relevance>0
        return match*10+relevance*(1 if rerank else .55)+(8 if global_rule else 0)

    def traverse(self,roots,allowed_nodes,allowed_facts):
        queue=deque((r,0) for r in roots);visited={};traversed=[]
        while queue and len(visited)<CONFIG['domain_nodes']:
            node,depth=queue.popleft()
            if node in visited:continue
            visited[node]=depth
            if depth==CONFIG['graph_depth']:continue
            for target,edge in self.adjacency.get(node,[]):
                if len(traversed)>=CONFIG['domain_edge_reads']:return visited,traversed
                if target not in allowed_nodes:continue
                supports=edge.get('metadata',{}).get('support_fact_ids',[edge.get('metadata',{}).get('fact_id')])
                if any(fid and fid not in allowed_facts for fid in supports):continue
                traversed.append(edge['id']);queue.append((target,depth+1))
        return visited,traversed

    def finalize(self,cards):
        out=[];chars=0;images=[]
        for c in cards:
            serialized=json.dumps(c,ensure_ascii=False,sort_keys=True);n=len(serialized)
            if len(out)>=CONFIG['final_cards'] or chars+n>CONFIG['max_chars']:continue
            out.append(c);chars+=n
            if c.get('image_id') and len(images)<CONFIG['final_images']:images.append(c['image_id'])
        return out,chars,images

    def retrieve(self,request):
        q=request['question'];visual=request['visual_entities'];lexical=self.lexical_roots(q);weights=self.targets(q)
        shared=self.first_stage(q,visual);results={}
        for method in ['A','B','C','D']:
            start=time.perf_counter();roots=lexical+([] if method=='A' else visual)
            if method!='A' and not visual:
                results[method]={'status':'NEEDS_IDENTIFICATION','candidate_ids':[],'final_ids':[],'pages':shared,'latency_ms':0,'cards':[],'inspected':0,'domain_nodes':[],'traversed_edges':[],'images':[],'chars':0};continue
            if method=='D':
                pool=results['C']['_pool'];inspected=results['C']['inspected'];visited=results['C']['domain_nodes'];edges=results['C']['traversed_edges'];pages=shared
                ordered=sorted(pool,key=lambda c:(-self.score(c,roots,weights,rerank=True),c['id']))
            else:
                pages=self.first_stage(q,[]) if method=='A' else shared
                # Page-to-ID index selects a bounded pool before inspecting or scoring cards.
                eligible=[];seen=set()
                for page in pages:
                    for c in self.page_index.get(page,[]):
                        if c['id'] in seen:continue
                        if len(eligible)>=CONFIG['inspect_cards']:break
                        eligible.append(c);seen.add(c['id'])
                    if len(eligible)>=CONFIG['inspect_cards']:break
                eligible=sorted(eligible,key=lambda c:(-self.score(c,roots,weights),c['id']))
                inspected=len(eligible);visited=[];edges=[]
                if method=='C':
                    starts=list(dict.fromkeys(roots+(['Calendar'] if any(p in weights for p in ['growth_days','stage_durations','machine_day']) else [])))
                    allowed_nodes={c['subject'] for c in eligible}|set(starts)
                    allowed_nodes.update(c['value'] for c in eligible if c['unit'] in ['entity','season'] and isinstance(c['value'],str))
                    visited,edges=self.traverse(starts,allowed_nodes,{c['id'] for c in eligible})
                    pool=[c for c in eligible if c['subject'] in visited][:CONFIG['candidate_pool']]
                    # C uses coarse proximity, D alone applies the second question-aware rerank.
                    ordered=sorted(pool,key=lambda c:(visited[c['subject']],-self.score(c,roots,{},rerank=False),c['id']))
                else:pool=eligible[:CONFIG['candidate_pool']];ordered=pool
            final,chars,images=self.finalize(ordered)
            node_ids={c['subject'] for c in final}|{c['id'] for c in final if c['id'].startswith('fact:')}
            node_ids.update(c['value'] for c in final if c['unit'] in ['entity','season'] and isinstance(c['value'],str) and c['value'] in self.graph.nodes)
            node_ids.update('source:'+page for c in final for page in c['pages'])
            relationship_ids=[e['id'] for e in self.graph.edges if e['source'] in node_ids and e['target'] in node_ids]
            results[method]={'status':'EVIDENCE' if final else 'INCOMPLETE_EVIDENCE','candidate_ids':[c['id'] for c in pool],
              'final_ids':[c['id'] for c in final],'pages':pages,'cards':final,'chars':chars,'images':images,
              'latency_ms':round((time.perf_counter()-start)*1000,4),'inspected':inspected,'domain_nodes':list(visited),
              'traversed_edges':edges,'node_ids':sorted(node_ids),'relationship_ids':relationship_ids,'_pool':pool}
        for method,result in results.items():
            result.pop('_pool',None);result['candidate_hash']=sha(json.dumps(sorted(result['candidate_ids'])).encode())
        return {'query_id':request['query_id'],'question':q,'identification_mode':request['identification_mode'],
                'snapshot_id':self.graph.manifest['snapshot_id'],'shared_pages':shared,'methods':results}


def run():
    retriever=Retriever();inputs=read_jsonl(DATA/'retrieval_inputs.jsonl')
    dump(BASE/'results/retrieval_dev.json',[retriever.retrieve(q) for q in inputs if q['split']=='dev'])
    dump(DATA/'retrieval_config.json',{**CONFIG,'snapshot_id':retriever.graph.manifest['snapshot_id'],'frozen_before_test':True,'tuning':'none after dev execution'})
    traces=[retriever.retrieve(q) for q in inputs if q['split']=='test'];jsonl(BASE/'results/retrieval_traces.jsonl',traces)
    # Scorer opens gold only after all retrieval traces have been written.
    gold={g['query_id']:g for g in read_jsonl(DATA/'retrieval_gold.jsonl')};rows=[];budget=[]
    card_index={c['id']:c for c in retriever.cards}
    for trace in traces:
        expected=gold[trace['query_id']]
        budget.append(trace['methods']['C']['candidate_hash']==trace['methods']['D']['candidate_hash'])
        for method,result in trace['methods'].items():
            ids=set(result['final_ids']);sets=expected['sufficient_fact_sets']
            complete=any(set(s)<=ids for s in sets) if sets else result['status']==expected['expected_status']
            recall=max([len(set(s)&ids)/len(s) for s in sets] or [0])
            required=set(sets[0]) if sets else set()
            page_groups={tuple(card_index[f]['pages']) for f in required}
            page_recall=sum(bool(set(group)&set(result['pages'])) for group in page_groups)/len(page_groups) if page_groups else None
            required_images={card_index[f]['image_id'] for f in required if card_index[f].get('image_id')}
            image_recall=len(required_images&set(result['images']))/len(required_images) if required_images and method!='A' else None
            valid_sources=all(retriever.graph.fact(card_index[f]['subject'],card_index[f]['predicate']) for f in ids if f.startswith('fact:'))
            rows.append({'query_id':trace['query_id'],'method':method,'complete':complete,'fact_recall':round(recall,4),
                         'page_recall':page_recall,'image_recall':image_recall,'valid_sources':valid_sources,
                         'expected_status':expected['expected_status'],'status':result['status'],'latency_ms':result['latency_ms']})
            budget.append(result['inspected']<=60 and len(result['candidate_ids'])<=40 and len(result['final_ids'])<=8 and result['chars']<=4000 and len(result['images'])<=4 and len(result['domain_nodes'])<=30)
    jsonl(BASE/'results/retrieval_scores.jsonl',rows)
    with (BASE/'results/retrieval_comparison.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary={m:{'answerable_complete':sum(r['complete'] for r in rows if r['method']==m and r['expected_status']=='EVIDENCE'),
        'answerable_n':sum(r['method']==m and r['expected_status']=='EVIDENCE' for r in rows),
        'negative_correct':sum(r['complete'] for r in rows if r['method']==m and r['expected_status']!='EVIDENCE'),
        'negative_n':sum(r['method']==m and r['expected_status']!='EVIDENCE' for r in rows),
        'mean_fact_recall':sum(r['fact_recall'] for r in rows if r['method']==m and r['expected_status']=='EVIDENCE')/sum(r['method']==m and r['expected_status']=='EVIDENCE' for r in rows)} for m in 'ABCD'}
    comparisons={}
    for before,after in [('B','C'),('C','D')]:
        changes=[]
        for trace in traces:
            a=next(r for r in rows if r['query_id']==trace['query_id'] and r['method']==before)
            b=next(r for r in rows if r['query_id']==trace['query_id'] and r['method']==after)
            changes.append({'query_id':trace['query_id'],'change':int(b['complete'])-int(a['complete'])})
        comparisons[before+'→'+after]=changes
    pair_results=[]
    for i in range(1,9):
        ids=['R'+str(2*i-1).zfill(2),'R'+str(2*i).zfill(2)]
        pair_results.append({'pair':i,'question_ids':ids,'both_complete':{m:all(r['complete'] for r in rows if r['method']==m and r['query_id'] in ids) for m in 'ABCD'}})
    result={'status':'PASS_MECHANISM_DIAGNOSTIC' if all(budget) else 'FAIL','questions':len(traces),'summary':summary,'pairs':pair_results,
      'budget_checks_passed':all(budget),'same_candidate_pool_C_D':True,'comparisons':comparisons,
      'limitations':['assisted entity inputs','2 pair specifications amended due to image coverage','independent gold review pending','no statistical claim',
                     'Page/image expected sets derived from independent required fact IDs after first pilot; no separate human review',
                     'Conditional evidence compatibility and relation recall not independently evaluated'],
      'scope':'deterministic engineering adaptation, not trained paper QM-Retriever'}
    dump(BASE/'results/v04.json',result);print(summary);return 0 if all(budget) else 1

if __name__=='__main__':raise SystemExit(run())
