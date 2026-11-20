"""One measurable model-visible evidence budget, separate from audit metadata."""
from .core import canonical, digest

BUDGET_DEFINITION = {
    'version': 'model-visible-evidence/v1',
    'unit': 'Unicode code points in core.canonical(model_payload)',
    'includes': ['complete selected fact/relation values and conditions', 'selected entity identities',
                 'complete source quotations and citations', 'image references', 'bundle/status/snapshot envelope',
                 'compact trace and already-seen references'],
    'excludes': ['user question and dialogue history', 'system/tool schemas', 'binary image bodies',
                 'server-only audit trace and provenance hashes'],
    'scope': '6000 per initial retrieval or explicit supplementation payload, not total conversation context',
    'supplements': 'New complete evidence plus references to previously visible immutable evidence; cumulative characters reported separately',
}
BUDGET_DEFINITION_HASH = digest(BUDGET_DEFINITION)


def chars(value):
    return len(canonical(value))


def project(row, fields):
    return {key: row[key] for key in fields if key in row}


def graph_payload(body, trace, *, phase='initial', seen_records=(), seen_evidence=(), seen_entities=(), seen_assets=()):
    seen_records, seen_evidence, seen_entities, seen_assets = map(set, (seen_records, seen_evidence, seen_entities, seen_assets))
    facts = [project(row, ('id','subject','predicate','value','unit','conditions','evidence_ids','review_status'))
             for row in body['facts'] if row['id'] not in seen_records]
    relations = [project(row, ('id','subject','predicate','object','direction','conditions','evidence_ids','review_status'))
                 for row in body['relations'] if row['id'] not in seen_records]
    entities = [project(row, ('id','name','type','aliases')) for row in body['entities'] if row['id'] not in seen_entities]
    evidence = [project(row, ('id','page_id','quote','url','locator','revision_id'))
                for row in body['evidence_refs'] if row['id'] not in seen_evidence]
    images = []
    for asset in body['assets']:
        if asset['id'] in seen_assets:continue
        regions = [row for row in body['regions'] if row['asset_id'] == asset['id']]
        region_ids = {row['id'] for row in regions}
        aligns = [project(row, ('id','region_ids','target_kind','target_id','evidence_ids','confirmation_level','review_status'))
                  for row in body['alignments'] if region_ids & set(row['region_ids'])]
        images.append({'asset_id':asset['id'], 'url':asset.get('url'),
                       'regions':[project(row, ('id','bbox')) for row in regions], 'alignments':aligns})
    payload = {'bundle_id':body['bundle_id'], 'snapshot_id':body['snapshot_id'],
        'status':'CANDIDATE_EVIDENCE' if body['execution_mode']=='candidate_diagnostic' else 'EVIDENCE',
        'facts':facts, 'relations':relations, 'entities':entities, 'evidence_refs':evidence, 'image_evidence':images,
        'trace':{'trace_id':trace['trace_id'], 'method':trace.get('method',trace.get('operation')), 'phase':phase,
                 'budget_definition_hash':BUDGET_DEFINITION_HASH}}
    if phase != 'initial':
        payload['already_seen_record_refs'] = sorted(seen_records & {r['id'] for r in body['facts']+body['relations']})
        payload['already_seen_evidence_refs'] = sorted(seen_evidence & {r['id'] for r in body['evidence_refs']})
    return payload


def product_payload(chunks, images):
    return {'source_chunks':[project(row, ('id','page_id','text','locator','url')) for row in chunks],
            'image_evidence':images, 'status':'CANDIDATE_SOURCE_EVIDENCE',
            'trace':{'method':'original_source_text_image_rag/v1', 'phase':'initial',
                     'budget_definition_hash':BUDGET_DEFINITION_HASH}}
