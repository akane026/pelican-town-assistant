import copy
import pytest
from pathlib import Path
from stardew_agent.core import *
from stardew_agent.parsing import *
from stardew_agent.construction import merge_graphs
from stardew_agent.visual import pixel_observation

def sample():
    s=read(DATA/'manifests/sources.json');a=read(DATA/'manifests/assets.json')
    return parse_page(next(x for x in s if x['page_id']=='Parsnip'),a),a

def test_real_stage_headers_values_and_identity():
    b,a=sample();g=extract_structural(b,a)
    stages=[n for n in g['entities'] if n['type']=='CropStage']
    assert len(stages)==5
    assert next(f['value'] for f in g['facts'] if f['predicate']=='stage_durations')==[1,1,1,1]
    assert len([r for r in g['relations'] if r['predicate']=='NEXT_STAGE'])==4
    assert any(x['target_kind']=='state' for x in g['anchors'])

def test_template_new_name_no_crop_branch(tmp_path):
    # Synthetic fixture explicitly, not a real new crop or held-out corpus result.
    html='<table id="infoboxtable"><tr><td id="infoboxsection">Seed</td><td>Fixture Seeds</td></tr><tr><td id="infoboxsection">Growth Time</td><td>9 days</td></tr><tr><td id="infoboxsection">Season</td><td>Summer</td></tr></table>'
    p=tmp_path/'fixture.html';p.write_text(html)
    source={'page_id':'Synthetic_Fixture','revision_id':'synthetic','sha256':file_hash(p),'raw_path':str(p),'url':'https://example.invalid/fixture'}
    b=parse_page(source,[]);g=extract_structural(b,[])
    assert next(f['value'] for f in g['facts'] if f['predicate']=='growth_days')==9

def test_directed_multi_predicate_ids():
    a=relation('a','P','b',['e']);b=relation('b','P','a',['e']);c=relation('a','Q','b',['e']);d=relation('a','P','b',['e'],{'quality':'gold'})
    assert len({x['id'] for x in (a,b,c,d)})==4

@pytest.mark.parametrize('box',[[0,0,0,1],[-.1,0,1,1],[0,0,2,1],[0,0,float('nan'),1],[1,0,0,1]])
def test_bad_boxes_rejected(box):
    with pytest.raises(ValidationError):validate_bbox(box)

def test_real_pixels_are_read_and_hash_checked():
    a=read(DATA/'manifests/assets.json')[0];o,rs=pixel_observation(a)
    assert o['pixel_statistics']['opaque_fraction']>0
    assert o['input_image_sha256']==file_hash(ROOT/a['path'])
    with pytest.raises(ValidationError):pixel_observation({**a,'sha256':'bad'})

def test_empty_visual_relations_legal_and_conflicts_not_overwritten():
    b,a=sample();g=extract_structural(b,a);g['anchors']=[]
    one=copy.deepcopy(g['facts'][0]);one['id']='fact:synthetic-conflict';one['value']=999;g['facts'].append(one)
    result=merge_graphs([g])
    assert result['conflicts'] and sum(f['review_status']=='conflicted' for f in result['facts'])==2
    assert result['observations']==[]

def test_source_mutation_rejected(tmp_path):
    b,_=sample();p=tmp_path/'changed.html';p.write_text('<p>changed</p>')
    with pytest.raises(ValidationError):parse_page({**b['source'],'raw_path':str(p)},[])
