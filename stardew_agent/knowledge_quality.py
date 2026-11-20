"""Structural and visual-contract checks, separate from human semantic review."""
from collections import Counter
from .core import ValidationError, validate_bbox
from .capabilities import GROUPS, audit_release_dependencies
from .normalization import CANONICAL_TYPES, FACT_PREDICATES, RELATION_PREDICATES


def validate_visual_links(domain, strict=False):
    indexes={k:{r['id']:r for r in domain.get(k,[])} for k in GROUPS};issues=[]
    def fail(code, row):raise ValidationError(code+':'+row['id'])
    for obs in domain.get('observations',[]):
        if obs['asset_id'] not in indexes['assets']:fail('OBSERVATION_ASSET',obs)
        object_ids=set()
        for obj in obs.get('objects',[]):
            region=indexes['regions'].get(obj.get('region_id'))
            if region is None:fail('OBSERVATION_REGION',obs)
            if region['asset_id']!=obs['asset_id']:fail('OBSERVATION_CROSS_ASSET',obs)
            if obj.get('object_id') in object_ids:fail('OBSERVATION_DUPLICATE_OBJECT',obs)
            object_ids.add(obj.get('object_id'))
            if 'bbox_normalized_xyxy' in obj:
                validate_bbox(obj['bbox_normalized_xyxy'])
                if obj['bbox_normalized_xyxy']!=region['bbox']:fail('OBSERVATION_BBOX_MISMATCH',obs)
        for rel in obs.get('relations',[]):
            if rel.get('subject') not in object_ids or rel.get('object') not in object_ids:fail('VISUAL_RELATION_ENDPOINT',obs)
    for alignment in domain.get('alignments',[]):
        occurrence_ids=list(dict.fromkeys([alignment.get('occurrence_id')]+alignment.get('support_occurrence_ids',[])))
        occs=[indexes['occurrences'].get(i) for i in occurrence_ids if i]
        if any(o is None for o in occs):fail('ALIGNMENT_SUPPORT_OCCURRENCE',alignment)
        assets={o.get('asset_id') for o in occs if o}
        regions=[indexes['regions'].get(i) for i in alignment.get('region_ids',[])]
        if any(r is None for r in regions):fail('ALIGNMENT_REGION',alignment)
        if assets and any(r['asset_id'] not in assets for r in regions):fail('ALIGNMENT_CROSS_ASSET',alignment)
        if alignment.get('page_id') and any(o.get('page_id') and o['page_id']!=alignment['page_id'] for o in occs):fail('ALIGNMENT_CONTEXT_PAGE',alignment)
        obs=indexes['observations'].get(alignment.get('observation_id'))
        if alignment.get('observation_id') and obs is None:fail('ALIGNMENT_OBSERVATION',alignment)
        if obs and (assets and obs['asset_id'] not in assets or not any(r['asset_id']==obs['asset_id'] for r in regions)):
            fail('ALIGNMENT_OBSERVATION_CROSS_ASSET',alignment)
        level=alignment.get('confirmation_level')
        if level=='visual_checked':
            object_regions={o['region_id'] for o in obs.get('objects',[])} if obs else set()
            if not regions or not set(alignment['region_ids'])<=object_regions:fail('MODEL_ALIGNMENT_OBJECT_ROI_REQUIRED',alignment)
            if not obs or obs.get('method')!='ChatECNU_visual/v1':fail('MODEL_ALIGNMENT_OBSERVATION_REQUIRED',alignment)
            if any(r.get('method')=='whole_image/v1' for r in regions):fail('MODEL_ALIGNMENT_OBJECT_ROI_REQUIRED',alignment)
            if alignment.get('status')!='matched':fail('VISUAL_CONFIRMATION_STATUS',alignment)
        elif 'mllm_alignment' in alignment.get('method',''):
            issues.append({'code':'MODEL_ALIGNMENT_NOT_VISUALLY_CONFIRMED','id':alignment['id']})
            if strict:fail('MODEL_ALIGNMENT_OBJECT_ROI_REQUIRED',alignment)
    return {'status':'PASS','issues':issues,'checked_observations':len(indexes['observations']),'checked_alignments':len(indexes['alignments'])}


def audit_graph(domain):
    from .core import validate_graph
    validate_graph(domain);visual=validate_visual_links(domain)
    issues=list(visual['issues'])
    for row in domain.get('entities',[]):
        if row['type'] not in CANONICAL_TYPES:issues.append({'code':'UNKNOWN_ENTITY_TYPE','id':row['id'],'value':row['type']})
    for group,known in [('facts',FACT_PREDICATES),('relations',RELATION_PREDICATES)]:
        for row in domain.get(group,[]):
            if row['predicate'] not in known:issues.append({'code':'UNKNOWN_PREDICATE','id':row['id'],'value':row['predicate']})
    # Treat every critical record as hypothetically approved only for structural
    # dependency diagnostics. This does not change its actual review status.
    deps=audit_release_dependencies(domain,{r['id'] for k in ('facts','relations','alignments') for r in domain.get(k,[])})
    return {'schema':'graph-quality/v1','status':'CANDIDATE_REVIEW_REQUIRED','counts':{k:len(domain.get(k,[])) for k in GROUPS},
            'types':dict(Counter(r['type'] for r in domain.get('entities',[]))),
            'confirmation_levels':dict(Counter(r.get('confirmation_level','legacy_unspecified') for r in domain.get('alignments',[]))),
            'issues':issues,'visual_links':visual,'dependency_audit':deps,
            'limitations':['Structural checks and model agreement are not human semantic ground truth.']}
