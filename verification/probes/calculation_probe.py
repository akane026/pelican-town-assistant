"""Independent literal expectations plus graph intervention tests."""
import copy
from pathlib import Path
from verification.common import BASE, DATA, assert_record, dump, file_sha, jsonl, load, now, offline_guard, sha
from verification.graph import GRAPH, KnowledgeGraph, EvidenceError
from verification.calculators import *


def override_graph(name,mutator):
    from semantica.provenance import ProvenanceManager
    directory=BASE/'artifacts/interventions'/name;directory.mkdir(parents=True,exist_ok=True)
    graph=load(GRAPH/'graph.json');mutator(graph)
    dump(directory/'graph.json',graph)
    db=directory/'provenance.sqlite3'
    if db.exists():db.unlink()
    pm=ProvenanceManager(storage_path=str(db))
    for n in graph['entities']:
        if n['type']=='Fact':
            f=n['metadata'];ev=f['evidence'][0]
            if pm.track_entity(entity_id=f['id'],source=ev['url'],source_location=ev['location'],source_quote=ev['quote'],
               entity_type='Fact',metadata={'fact':f,'test_override':name}) is None:raise EvidenceError('override write failed')
    m=load(GRAPH/'manifest.json');m.update(snapshot_id='test_override:'+name+':'+file_sha(directory/'graph.json')[:16],
      test_override=True,reason=name,graph_sha256=file_sha(directory/'graph.json'),provenance_sha256=file_sha(db))
    dump(directory/'manifest.json',m);return KnowledgeGraph(directory)


def run():
    offline_guard();checks=[];rows=[];g=KnowledgeGraph()
    def check(group,name,actual,expected):
        assert_record(checks,name,actual==expected,{'actual':actual,'expected':expected,'group':group})
    def error(group,name,call,expected):
        try:call();actual='NO_ERROR'
        except TaskError as e:actual=e.status
        except EvidenceError:actual='INCOMPLETE_EVIDENCE'
        check(group,name,actual,expected)
    params={'day':23,'plants':50,'season':'Spring','watered':True}
    base=EvidenceResolver(g).planting('Parsnip_Seeds',**params);rows.append({'case':'C01','actual':base})
    check('C01','spring_23_parsnip',base['result'],{'status':'OK','harvest_days':[27],'units':50,'seed_cost_g':1000,'sales_g':1750,'margin_after_seed_g':750,'random_extra_yield':'excluded'})
    check('C01','deterministic_repeat',EvidenceResolver(g).planting('Parsnip_Seeds',**params),base)
    check('C02','last_valid_planting',EvidenceResolver(g).planting('Parsnip_Seeds',**{**params,'day':24})['result']['harvest_days'],[28])
    check('C02','late_planting',EvidenceResolver(g).planting('Parsnip_Seeds',**{**params,'day':25})['result']['status'],'NO_HARVEST')
    blueberry=EvidenceResolver(g).planting('Blueberry_Seeds',day=1,plants=2,season='Summer',watered=True)
    check('C03','regrowth_harvest_days',blueberry['result']['harvest_days'],[14,18,22,26])
    check('C03','base_blueberry_yield',blueberry['result']['units'],24)
    formula=g.fact('Jelly','value_formula')['value']
    processed=process_value(g.fact('Melon','sell_normal')['value'],g.fact('Melon','sell_gold')['value'],**formula,quantity=2)
    check('C04','quality_opportunity_cost',processed,{'unit_value_g':550,'sales_g':1100,'raw_opportunity_cost_g':750,'incremental_value_g':350,'profit_after_historical_cost_g':None})
    ds=g.fact('Melon','stage_durations')['value'];check('C05','stage4_range',stage_remaining(ds,4),[4,6]);check('C05','mature_zero',stage_remaining(ds,6),[0,0])
    check('C06','consistent_date',stage_date_consistent(ds,4,7),True)
    error('C06','conflicting_date',lambda:stage_date_consistent(ds,4,2),'CONFLICT')
    day_minutes=g.fact('Calendar','machine_day')['value'];jar_minutes=g.fact('Jelly','processing_minutes')['value']
    machine=daily_machine_batches(1,10,jar_minutes,day_minutes,2)
    check('C07','daily_operation_batches',machine['collection_days'],[4,7,10]);check('C07','deadline_inclusive',machine['completed_items'],6)
    check('C07','deadline_exclusive',daily_machine_batches(1,10,jar_minutes,day_minutes,2,include_deadline=False)['completed_items'],4)
    check('C07','wine_06_collection',daily_machine_batches(1,8,g.fact('Wine','processing_minutes')['value'],day_minutes,1)['collection_days'],[8])
    check('C08','shared_inventory_remaining',allocate(10,{'bundle':5,'process':3}),2)
    error('C08','double_allocation',lambda:allocate(10,{'bundle':5,'process':6}),'INSUFFICIENT_INVENTORY')
    req=g.fact('Quality_Crops_Bundle','requirements')['value'];k=g.fact('Quality_Crops_Bundle','choose_k')['value']
    check('C09','choose_three_with_one_complete',bundle_combinations(req,k,['Parsnip'],{'Melon':{'gold':5},'Corn':{'iridium':5},'Pumpkin':{'gold':0}}),[['Melon','Corn']])
    check('C09','normal_quality_not_accepted',bundle_combinations(req,k,[],{'Parsnip':{'normal':50}}),[])
    mats=g.fact('Keg','materials')['value'];lvl=g.fact('Keg','farming_level')['value']
    crafted=crafting(mats,2,{'Wood':40,'Copper_Bar':2,'Iron_Bar':1,'Oak_Resin':0},lvl,8,1)
    check('C10','two_keg_materials',crafted,{'missing_materials':{'Wood':20,'Copper_Bar':0,'Iron_Bar':1,'Oak_Resin':2},'can_craft':False,'existing_usable':1})
    error('C10','unknown_unlock',lambda:crafting(mats,1,{},lvl,None),'NEEDS_INPUT')
    for value in [-1,1.2,True]:error('C11','invalid_quantity_'+str(value),lambda v=value:EvidenceResolver(g).planting('Parsnip_Seeds',**{**params,'plants':v}),'INVALID_INPUT')
    for key in ['day','plants','season','watered']:error('C11','missing_'+key,lambda k=key:EvidenceResolver(g).planting('Parsnip_Seeds',**{**params,k:None}),'NEEDS_INPUT')
    error('C12','accelerated_growth',lambda:EvidenceResolver(g).planting('Parsnip_Seeds',**params,acceleration='speed_gro'),'UNSUPPORTED_CONDITIONS')
    error('C12','unverified_release',lambda:g.fact('Parsnip','growth_days',require_release=True),'INCOMPLETE_EVIDENCE')
    def change_fact(graph,id,callback):
        callback(next(n['metadata'] for n in graph['entities'] if n['id']==id))
    changed=override_graph('related_price',lambda gr:change_fact(gr,'fact:Parsnip:sell_normal',lambda f:f.update(value=40,test_override={'original_value':35,'purpose':'causal test, not Wiki fact'})))
    after=EvidenceResolver(changed).planting('Parsnip_Seeds',**params)
    check('C12','related_price_changes_margin',after['result']['margin_after_seed_g'],1000)
    check('C12','override_snapshot_exposed',after['trace']['snapshot_id'].startswith('test_override:'),True)
    unrelated=override_graph('unrelated_price',lambda gr:change_fact(gr,'fact:Melon:sell_normal',lambda f:f.update(value=999,test_override=True)))
    check('C12','unrelated_fact_no_effect',EvidenceResolver(unrelated).planting('Parsnip_Seeds',**params)['result'],base['result'])
    def bad_sources(f):
        for ev in f['evidence']:ev['raw_path']='data/raw/does-not-exist.html'
    missing=override_graph('missing_unique_source',lambda gr:change_fact(gr,'fact:Parsnip:growth_days',bad_sources))
    error('C12','missing_unique_source_blocks',lambda:EvidenceResolver(missing).planting('Parsnip_Seeds',**params),'INCOMPLETE_EVIDENCE')
    redundant=override_graph('missing_redundant_source',lambda gr:change_fact(gr,'fact:Jelly:value_formula',lambda f:f['evidence'][0].update(raw_path='data/raw/missing.html')))
    check('C12','redundant_source_survives',len(redundant.fact('Jelly','value_formula')['evidence']),1)
    corrupt=override_graph('bad_source_hash',lambda gr:change_fact(gr,'fact:Parsnip:growth_days',lambda f:f['evidence'][0].update(source_sha256='0'*64)))
    error('C12','source_hash_corruption',lambda:corrupt.fact('Parsnip','growth_days'),'INCOMPLETE_EVIDENCE')
    missingunit=override_graph('missing_unit',lambda gr:change_fact(gr,'fact:Parsnip:growth_days',lambda f:f.update(unit='')))
    error('C12','missing_unit_rejected',lambda:EvidenceResolver(missingunit).planting('Parsnip_Seeds',**params),'INCOMPLETE_EVIDENCE')
    error('C12','stale_index_rejected',lambda:KnowledgeGraph(changed.directory,expected_snapshot=g.manifest['snapshot_id']),'INCOMPLETE_EVIDENCE')
    # A deleted unique graph edge must prevent the resolver from silently using the fact alone.
    noedge=override_graph('deleted_seed_edge',lambda gr:gr.update(relationships=[e for e in gr['relationships'] if not (e['source']=='Parsnip_Seeds' and e['type']=='GROWS_INTO')]))
    error('C12','deleted_seed_edge_blocks',lambda:EvidenceResolver(noedge).planting('Parsnip_Seeds',**params),'INCOMPLETE_EVIDENCE')
    jsonl(BASE/'results/calculation_cases.jsonl',checks)
    jsonl(DATA/'calculation_gold.jsonl',[{'name':r['name'],'expected':r['detail']['expected'],'scenario':r['detail']['group'],
          'review_status':'literal manual arithmetic by same assistant; independent review pending'} for r in checks])
    dump(BASE/'artifacts/calculation_trace.json',{'baseline':base,'related_override':after,'blueberry':blueberry,'processing':processed})
    result={'status':'PASS_DIAGNOSTIC' if all(c['passed'] for c in checks) else 'FAIL','assertions':checks,'scenario_groups':12,
      'at':now(),'independent_human_review':'pending','game_version':'unverified; frozen Wiki snapshot only',
      'gold_origin':'literal manual arithmetic, separately asserted; same assistant, no independent reviewer'}
    dump(BASE/'results/v05.json',result);print(result['status'],len(checks));return int(result['status']=='FAIL')

if __name__=='__main__':raise SystemExit(run())
