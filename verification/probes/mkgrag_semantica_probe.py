"""Focused audit of the actual Semantica -> multimodal graph retrieval handoff."""
from verification.common import BASE, DATA, assert_record, dump, file_sha, load, read_jsonl
from verification.graph import KnowledgeGraph
from verification.retrieval import Retriever
from verification.vision import VisualRetriever


def main():
    graph=KnowledgeGraph();retriever=Retriever(graph);checks=[]
    def check(name,value,detail=None):assert_record(checks,name,value,detail)
    manifest=load(DATA/'knowledge_manifest.json')
    check('semantica_export_snapshot_matches_inputs',graph.manifest['snapshot_id']==manifest['snapshot_id'])
    check('real_builder_and_independent_reload_passed',load(BASE/'results/v02.json')['status']=='PASS')
    seed='Parsnip_Seeds';crop=graph.seed_crop(seed)
    path=[]
    for src,dst,kind in [(seed,crop,'GROWS_INTO'),(crop,'fact:Parsnip:growth_days','HAS_FACT'),
                         ('fact:Parsnip:growth_days','source:Parsnip','SUPPORTED_BY')]:
        matches=[e for e in graph.edges if (e['source'],e['target'],e['type'])==(src,dst,kind)]
        check('path_edge_'+kind,len(matches)==1);path.extend(matches)
    fact=graph.fact(crop,'growth_days');check('fact_has_value_unit_quote_and_revision',fact['value']==4 and fact['unit']=='growth_nights' and 'oldid=' in fact['evidence'][0]['url'])
    check('crop_category_supports_processing',graph.fact('Melon','category')['value']=='fruit' and graph.fact('Parsnip','category')['value']=='vegetable')
    check('season_is_explicit_graph_relation',graph.targets('Parsnip','GROWS_IN_SEASON')==['Spring'])
    sample=next(r for r in read_jsonl(DATA/'visual_test_manifest.jsonl') if r['sample_id']=='V28')
    visual=VisualRetriever().candidates(BASE/sample['path'],'item')
    check('real_screenshot_pixels_retrieve_seed',visual['candidates'][0]['entity']==seed)
    gallery=next(r for r in read_jsonl(DATA/'gallery.jsonl') if r['entity']==seed)
    check('candidate_has_real_wiki_image',bool(gallery['occurrence_ids']) and file_sha(BASE/gallery['path'])==gallery['sha256'])
    check('image_occurrences_exist_in_semantica_graph',all(o in graph.nodes for o in gallery['occurrence_ids']))
    inputs={r['query_id']:r for r in read_jsonl(DATA/'retrieval_inputs.jsonl')}
    one=retriever.retrieve(inputs['R01']);two=retriever.retrieve(inputs['R02'])
    check('same_image_different_question_control',inputs['R01']['image_sha256']==inputs['R02']['image_sha256'] and inputs['R01']['player_state']==inputs['R02']['player_state'] and inputs['R01']['question']!=inputs['R02']['question'])
    check('question_changes_final_evidence',set(one['methods']['D']['final_ids'])!=set(two['methods']['D']['final_ids']))
    check('identity_question_has_entity_card','entity:Parsnip_Seeds' in one['methods']['D']['final_ids'])
    required={'fact:Parsnip_Seeds:grows_into','fact:Parsnip:season','fact:Parsnip:growth_days','fact:Calendar:watered_growth'}
    check('growth_question_has_sufficient_evidence',required<=set(two['methods']['D']['final_ids']))
    edges={e['id']:e for e in graph.edges};card_index={c['id']:c for c in retriever.cards}
    c=two['methods']['C'];d=two['methods']['D']
    check('entity_granularity',seed in d['node_ids'])
    check('relation_granularity',any(edges[e]['type']=='GROWS_INTO' for e in d['relationship_ids']))
    check('subgraph_granularity',len(c['domain_nodes'])>1 and bool(c['traversed_edges']) and all(e in edges for e in c['traversed_edges']))
    traces=read_jsonl(BASE/'results/retrieval_traces.jsonl')
    check('D_only_reranks_C_same_pool',all(t['methods']['C']['candidate_hash']==t['methods']['D']['candidate_hash'] for t in traces))
    check('second_stage_candidate_sources_within_first_stage',all(set(card_index[f]['pages'])&set(t['shared_pages']) for t in traces for f in t['methods']['C']['candidate_ids']))
    calc=load(BASE/'artifacts/calculation_trace.json')
    check('real_graph_price_intervention_changes_result',calc['baseline']['result']['margin_after_seed_g']==750 and calc['related_override']['result']['margin_after_seed_g']==1000)
    v05=load(BASE/'results/v05.json')
    check('deleting_graph_dependency_blocks_calculation',next(r for r in v05['assertions'] if r['name']=='deleted_seed_edge_blocks')['passed'])
    examples=[]
    galleries=read_jsonl(DATA/'gallery.jsonl')
    for crop in ['Parsnip','Melon','Blueberry']:
        examples.append({'type':'stage_sequence','subject':crop,'fact':graph.fact(crop,'stage_durations'),
          'images':[{'entity':r['entity'],'image_id':r['image_id'],'occurrences':r['occurrence_ids'][:2]} for r in galleries if r['entity'].startswith(crop+'_Stage_')],
          'alignment_origin':'html_layout; pixels are stage templates, sequence/durations come from table'})
    examples.append({'type':'bundle_slots','fact':graph.fact('Quality_Crops_Bundle','choose_k'),'alignment_origin':'HTML image occurrence count, not visual relation inference'})
    examples.append({'type':'machine_recipe','fact':graph.fact('Keg','materials'),'alignment_origin':'HTML infobox plus item images, not inferred from equipment pixels'})
    result={'status':'PASS_ADAPTED_PIPELINE' if all(c['passed'] for c in checks) else 'FAIL','assertions':checks,
      'snapshot_id':graph.manifest['snapshot_id'],'seed_source_path':path,'visual_input':sample['path'],'visual_result':visual,
      'seed_gallery_image':gallery,'same_image_queries':[one,two],'alignment_examples':examples,
      'scope':'Wiki-specific adaptation of mKG-RAG ideas on a real Semantica snapshot',
      'not_established':['original trained QM-Retriever/EGTR reproduction','pure-pixel extraction of domain relations','retrieval improvement over flat baseline','full data/version and independent-review gates']}
    dump(BASE/'results/mkgrag_semantica.json',result)
    print(result['status'],len(checks),'assertions');return int(result['status']=='FAIL')

if __name__=='__main__':raise SystemExit(main())
