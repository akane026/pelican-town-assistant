"""Synthetic contract negatives plus real frozen pixels; not semantic gold labels."""
import copy
import pytest
from stardew_agent.core import DATA, read, ident, validate_graph, ValidationError
from stardew_agent.construction import merge_graphs
from stardew_agent.visual import pixel_observation, align_graph
from stardew_agent.knowledge_quality import validate_visual_links


def fixture():
    asset=read(DATA/'manifests/assets.json')[0];obs,regions=pixel_observation(asset)
    g={k:[] for k in ('entities','facts','relations','evidence','assets','occurrences','regions','observations','alignments')}
    g.update(page_id='fixture',entities=[{'id':'entity:fixture','name':'Fixture','type':'Item','page_ids':['first'],'aliases':['old']}],
        assets=[asset],observations=[obs],regions=regions,evidence=[{'id':'evidence:fixture'}],
        occurrences=[{'id':'occurrence:fixture','asset_id':asset['id'],'page_id':'fixture','near_text':'Fixture source'}],
        anchors=[{'occurrence_id':'occurrence:fixture','target_kind':'entity','target_id':'entity:fixture','evidence_id':'evidence:fixture','role':'identity'}])
    g['alignments']=align_graph(g,[obs],regions)
    return g


def test_type_promotion_keeps_source_and_alias_union():
    g=fixture();other=copy.deepcopy(g);other['entities'][0].update(type='Crop',page_ids=['second'],aliases=['new'])
    row=merge_graphs([g,other])['entities'][0]
    assert row['type']=='Crop' and row['page_ids']==['first','second'] and row['aliases']==['new','old']


def test_structural_pixel_check_does_not_claim_semantic_confirmation():
    g=fixture();assert g['alignments'][0]['confirmation_level']=='structural_candidate'
    assert g['alignments'][0]['answer_allowed'] is False
    validate_graph(g)


@pytest.mark.parametrize('mutation',['region','observation','support_occurrence','bbox'])
def test_cross_asset_or_invalid_observation_rejected(mutation):
    g=fixture();other={**g['assets'][0],'id':'asset:other'};g['assets'].append(other)
    if mutation=='region':g['regions'][0]['asset_id']=other['id']
    elif mutation=='observation':g['observations'][0]['asset_id']=other['id']
    elif mutation=='support_occurrence':g['alignments'][0]['support_occurrence_ids']=['missing']
    else:g['observations'][0]['objects'][0]['bbox_normalized_xyxy']=[.1,.1,.8,.8]
    with pytest.raises(ValidationError):validate_graph(g)


@pytest.mark.parametrize('roi_answer',['valid','missing','foreign'])
def test_model_alignment_requires_actual_object_region(roi_answer):
    g=fixture();obs=g['observations'][0];whole=g['regions'][0]
    roi={**whole,'id':'region:fixture-roi','bbox':[.1,.1,.9,.9],'method':'mllm_candidate/v1'}
    g['regions'].append(roi);obs.update(method='ChatECNU_visual/v1',objects=[{'object_id':'object:0','region_id':roi['id'],'bbox_normalized_xyxy':roi['bbox']}])
    class ModelFixture:
        def structured(self,prompt,**kw):
            assert len(kw['images'])==1 and kw['context'][0]['image_index']==0
            answer={'occurrence_id':'occurrence:fixture','target_id':'entity:fixture','status':'matched','reason_summary':'Synthetic API fixture'}
            if roi_answer!='missing':answer['region_ids']=[roi['id'] if roi_answer=='valid' else 'region:foreign']
            return {'status':'OK','cache_key':'fixture','execution_mode':'synthetic_fixture','parsed':{'matches':[answer]}}
    g['alignments']=align_graph(g,g['observations'],g['regions'],ModelFixture())
    a=g['alignments'][0];validate_graph(g)
    assert a['confirmation_level']==('visual_checked' if roi_answer=='valid' else 'structural_candidate')
    if roi_answer=='valid':assert a['region_ids']==[roi['id']]
    else:assert g['alignment_validation_errors']


def test_whole_image_cannot_be_declared_visual_checked():
    g=fixture();g['alignments'][0]['confirmation_level']='visual_checked'
    with pytest.raises(ValidationError,match='MODEL_ALIGNMENT'):validate_visual_links(g)


def test_saved_roi_must_match_actual_source_crop(tmp_path,monkeypatch):
    from PIL import Image
    import stardew_agent.knowledge as knowledge
    from stardew_agent.core import file_hash
    # Real crop verification is independent of model claims and metadata hashes.
    source=tmp_path/'source.png';Image.new('RGB',(8,8),'red').save(source)
    crop=tmp_path/'crop.png';Image.new('RGB',(4,4),'blue').save(crop)
    monkeypatch.setattr(knowledge,'ROOT',tmp_path)
    monkeypatch.setattr(knowledge,'contained',lambda p:p)
    domain={'assets':[{'id':'asset:fixture','path':'source.png'}],
            'regions':[{'id':'region:fixture','asset_id':'asset:fixture','path':'crop.png','sha256':file_hash(crop),'bbox':[0,0,.5,.5]}]}
    with pytest.raises(ValidationError,match='REGION_PIXELS_MISMATCH'):knowledge.validate_region_files(domain)
    Image.new('RGB',(4,4),'red').save(crop);domain['regions'][0]['sha256']=file_hash(crop)
    assert knowledge.validate_region_files(domain)
