"""Assistant-reviewed public screenshot crops; gold is excluded from the matcher.

This is a diagnostic pilot, not the planned 48-image independently reviewed set.
One source capture is kept wholly in one split. Collection-menu icons are
labelled separately from inventory slots; none are screenshots from this PC.
"""
from PIL import Image, ImageDraw
from .common import BASE, DATA, dump, file_sha, jsonl, read_jsonl


def prepare():
    # bbox is in original screenshot pixels. Never resize or duplicate to increase counts.
    annotations=[
      ('autosaved_inventory','dev','item',(511,148,538,180),['Parsnip'],'quality star'),
      ('autosaved_inventory','dev','item',(602,148,631,180),['Parsnip'],'quantity overlay'),
      ('autosaved_inventory','dev','item',(480,148,511,180),[],'unknown potato'),
      ('autosaved_inventory','dev','item',(540,148,570,180),[],'unknown leek'),
      ('carls_beginning','dev','item',(335,6,360,33),['Parsnip_Seeds'],'tiny toolbar'),
      ('carls_beginning','dev','item',(215,6,240,33),[],'unknown axe'),
      ('forum_seed_shop','dev','item',(226,89,263,128),['Parsnip_Seeds'],'shop icon'),
      ('forum_seed_shop','dev','item',(226,222,263,263),[],'unknown cauliflower seeds'),
      ('forum_seed_shop','dev','item',(226,354,263,394),[],'unknown tulip seeds'),
      ('arqade_melon','dev','stage',(140,29,196,79),['Melon_Stage_3'],'crop identity from original question; sprite candidate'),
      ('arqade_melon','dev','stage',(204,295,263,352),[],'withered unknown'),
      ('3dm_inventory','test','item',(520,135,576,204),['Parsnip'],'collection icon'),
      ('3dm_inventory','test','item',(383,272,450,337),['Melon'],'collection icon'),
      ('3dm_inventory','test','item',(588,278,644,334),['Blueberry'],'collection icon'),
      ('3dm_inventory','test','item',(454,474,510,534),['Copper_Bar'],'collection icon'),
      ('3dm_inventory','test','item',(521,474,577,534),['Iron_Bar'],'collection icon'),
      ('3dm_inventory','test','item',(792,548,838,594),['Coal'],'collection icon'),
      ('3dm_inventory','test','item',(651,475,714,535),[],'unknown iridium bar'),
      ('3dm_inventory','test','item',(313,340,380,404),[],'unknown starfruit'),
      ('3dm_inventory','test','item',(315,138,381,204),[],'unknown daffodil'),
      ('3dm_inventory','test','item',(454,280,510,336),[],'unknown tomato'),
      ('9game_inventory','test','item',(479,30,514,75),['Parsnip'],'gold star and quantity'),
      ('9game_inventory','test','item',(648,234,687,280),['Parsnip'],'quantity overlay'),
      ('9game_inventory','test','item',(354,239,388,280),['Coal'],'quantity overlay'),
      ('9game_inventory','test','item',(438,32,471,74),['Wood'],'inventory item'),
      ('9game_inventory','test','item',(177,29,219,75),[],'unknown leek'),
      ('9game_inventory','test','item',(306,30,346,75),[],'unknown salmonberry'),
      ('steam_crafting','test','item',(375,452,438,522),['Parsnip_Seeds'],'quantity overlay'),
      ('steam_crafting','test','item',(56,451,118,522),[],'unknown axe'),
      ('korean_inventory','test','item',(900,322,965,388),['Parsnip_Seeds'],'quantity overlay; customized UI possible'),
      ('korean_inventory','test','item',(574,321,640,385),[],'unknown axe'),
      ('tom_melon','test','stage',(1468,345,1533,433),['Melon_Stage_6'],'mature crop'),
      ('tom_melon','test','stage',(514,375,569,432),['Melon_Stage_3'],'seedling; class review provisional'),
      ('tom_melon','test','stage',(1278,628,1341,680),[],'unknown seedling'),
      ('tom_melon','test','stage',(1206,690,1273,745),[],'unknown leafy crop'),
    ]
    sources={r['capture_id']:r for r in read_jsonl(DATA/'external_screenshot_manifest.jsonl')}
    rows=[];outdir=DATA/'visual_crops';outdir.mkdir(parents=True,exist_ok=True)
    for i,(capture,split,kind,box,labels,note) in enumerate(annotations,1):
        source=sources[capture];img=Image.open(BASE/source['path']).convert('RGB');crop=img.crop(box)
        sid=f'V{i:02}';path=outdir/(sid+'.png');crop.save(path)
        rows.append({'sample_id':sid,'capture_id':capture,'split':split,'kind':kind,'bbox':box,'path':str(path.relative_to(BASE)),
          'sha256':file_sha(path),'source_sha256':source['sha256'],'source_page':source['source_page'],
          'labels':labels,'unknown':not labels,'note':note,'ambiguous':kind=='stage' and 'Stage_3' in ' '.join(labels),
          'review_status':'assistant_visual_review; independent_human_pending','game_version':'unverified',
          'origin':'public_gameplay_screenshot','fixture':False,'stratum':'collection_menu' if capture=='3dm_inventory' else kind})
    jsonl(DATA/'visual_test_manifest.jsonl',rows)
    dump(DATA/'visual_pilot_freeze.json',{'manifest_sha256':file_sha(DATA/'visual_test_manifest.jsonl'),
      'notice':'35-crop diagnostic pilot; fails planned sample counts and independent-review prerequisite',
      'grouping':'source capture; no capture split across dev/test'})
    sheet=Image.new('RGB',(700,((len(rows)+6)//7)*125),'#eeeeee');d=ImageDraw.Draw(sheet)
    for i,r in enumerate(rows):
        im=Image.open(BASE/r['path']);im.thumbnail((90,85));x=i%7*100;y=i//7*125
        sheet.paste(im,(x,y+18));d.text((x,y),r['sample_id']+' '+r['split'],fill='black')
        d.text((x,y+103),(r['labels'][0] if r['labels'] else 'UNKNOWN').replace('Parsnip','P').replace('Melon','M')[:16],fill='black')
    sheet.save(BASE/'artifacts/visual_contact.png')
    print({'samples':len(rows),'captures':len({r['capture_id'] for r in rows}),
      'known_items':sum(not r['unknown'] and r['kind']=='item' for r in rows),
      'known_stages':sum(not r['unknown'] and r['kind']=='stage' for r in rows),'unknown':sum(r['unknown'] for r in rows)})

if __name__=='__main__':prepare()
