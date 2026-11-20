from types import SimpleNamespace
from PIL import Image
from stardew_agent.core import file_hash
from stardew_agent.online_vision import VisualMatcher

def test_actual_roi_pixels_and_cross_asset_ambiguity(tmp_path,monkeypatch):
    import stardew_agent.online_vision as vision
    monkeypatch.setattr(vision,'ROOT',tmp_path)
    records={k:{} for k in ('entities','assets','regions')};alignments=[]
    for i,background in enumerate(('red','blue')):
        path=tmp_path/f'{i}.png';im=Image.new('RGBA',(32,16),background)
        im.paste(Image.new('RGBA',(16,16),'lime'),(16,0));im.save(path)
        eid=f'entity:fixture_{i}';aid=f'asset:{i}';rid=f'region:{i}'
        records['entities'][eid]={'id':eid,'type':'Crop','name':eid}
        records['assets'][aid]={'id':aid,'path':path.name,'sha256':file_hash(path)}
        records['regions'][rid]={'id':rid,'asset_id':aid,'bbox':[.5,0,1,1]}
        alignments.append({'id':f'align:{i}','target_kind':'entity','target_id':eid,'status':'matched','region_ids':[rid]})
    matcher=VisualMatcher(SimpleNamespace(id='fixture',records=records,domain={'alignments':alignments}))
    query=tmp_path/'query.png';Image.new('RGB',(16,16),'lime').save(query)
    result=matcher.match(query)
    assert result['gallery_pixels']==1
    assert {x['entity_id'] for x in result['candidates']}==set(records['entities'])
    assert all(x['distance']==0 and x['shared_pixels'] for x in result['candidates'])
    assert result['status']=='NEEDS_CONFIRMATION'
    assert not result['automatic_identity_confirmation']
