"""Template-based Wiki parser. No crop-specific branches or fact value tables."""
from __future__ import annotations
import re
from pathlib import Path
from urllib.parse import urljoin,unquote,urlparse
from bs4 import BeautifulSoup
from .core import ROOT,DATA,SCHEMA,ident,digest,file_hash,read,write,rows,relation,ValidationError

def clean(s):return re.sub(r'\s+',' ',s).strip()
def entity_id(name):return 'entity:'+unquote(name).strip().replace(' ','_')
def norm_url(url):
    url=urljoin('https://stardewvalleywiki.com/',url)
    return re.sub(r'/thumb/(.+)/[^/]+$',r'/\1',url)
def own_rows(table):return [r for r in table.find_all('tr') if r.find_parent('table') is table]
def cells(row):return row.find_all(['th','td'],recursive=False)
def tx(node):return clean(node.get_text(' ',strip=True))
def linked_name(a):
    href=a.get('href','')
    if href.startswith('https://stardewvalleywiki.com/'):href=urlparse(href).path
    if not href.startswith('/') or href.startswith(('/mediawiki/','/File:','/Category:','/Special:')):return None
    return unquote(href.split('#')[0].strip('/')) or None

def import_legacy_manifest():
    manifest=[]
    for r in rows(ROOT/'verification/data/source_manifest.jsonl'):
        manifest.append({**r,'raw_path':'verification/'+r['raw_path'],'split':'development','batch':'baseline'})
    assets=[]
    for a in rows(ROOT/'verification/data/image_manifest.jsonl'):
        assets.append({**a,'id':'asset:'+a['sha256'],'path':'verification/'+a['path'],'source_kind':'original_wiki_asset'})
    write(DATA/'manifests/sources.json',manifest);write(DATA/'manifests/assets.json',assets)
    return manifest,assets

def parse_page(source,assets):
    path=ROOT/source['raw_path']
    if file_hash(path)!=source['sha256']:raise ValidationError('SOURCE_CHANGED:'+source['page_id'])
    soup=BeautifulSoup(path.read_text(encoding='utf-8'),'lxml')
    for n in soup.select('script,style,nav,.navbox,.mw-editsection,.toc,.printfooter'):n.decompose()
    tables=soup.find_all('table');table_ids={id(t):i for i,t in enumerate(tables)}
    lookup={norm_url(url):a for a in assets for url in [a['url']]+a.get('url_aliases',[])}
    page=source['page_id'];sid=ident('source',page,source['revision_id'],source['sha256'])
    sections=[]
    for i,n in enumerate(soup.select('h2,h3,h4')):
        sections.append({'id':ident('section',sid,i),'title':tx(n),'locator':n.get('id') or (n.find(id=True).get('id') if n.find(id=True) else f'heading[{i}]')})
    parsed=[]
    for i,t in enumerate(tables):
        heading=t.find_previous(['h2','h3','h4'])
        rr=[]
        for j,row in enumerate(own_rows(t)):
            cc=[]
            for k,c in enumerate(cells(row)):
                cc.append({'text':tx(c),'header':c.name=='th','rowspan':c.get('rowspan','1'),'colspan':c.get('colspan','1'),
                  'links':[{'name':linked_name(a),'text':tx(a)} for a in c.find_all('a') if linked_name(a)],
                  'image_urls':[norm_url(im.get('src','')) for im in c.find_all('img')],
                  'locator':f'table[{i}]/row[{j}]/cell[{k}]'})
            rr.append(cc)
        parsed.append({'id':ident('table',sid,i),'index':i,'heading':tx(heading) if heading else '',
                       'rows':rr,'text':tx(t),'locator':f'table[{i}]','nested':t.find_parent('table') is not None})
    occurrences=[]
    for i,im in enumerate(soup.find_all('img')):
        url=norm_url(im.get('src',''));asset=lookup.get(url)
        table=im.find_parent('table');row=im.find_parent('tr');cell=im.find_parent(['td','th']);a=im.find_parent('a')
        ti=table_ids.get(id(table));ri=next((j for j,r in enumerate(own_rows(table)) if r is row),None) if table else None
        ci=next((j for j,c in enumerate(cells(row)) if c is cell),None) if row else None
        sem_links=[linked_name(x) for x in (cell or im.parent).find_all('a') if linked_name(x)]
        occurrences.append({'id':ident('occurrence',sid,i,url,asset['id'] if asset else None),'page_id':page,'source_id':sid,'asset_id':asset['id'] if asset else None,
            'url':url,'locator':f'image[{i}]','alt':im.get('alt',''),'linked_name':(linked_name(a) if a else None) or (sem_links[0] if len(set(sem_links))==1 else None),
            'file_name_candidate':unquote(Path(urlparse(url).path).stem),
            'table_index':ti,'row_index':ri,'cell_index':ci,'near_text':tx(cell or im.parent)[:1500],
            'filter_reason':None if asset else 'asset_not_acquired'})
    blocks=[]
    for i,p in enumerate(soup.find_all(['p','li'])):
        if p.find_parent('table') or not tx(p):continue
        heading=p.find_previous(['h2','h3','h4'])
        blocks.append({'id':ident('block',sid,i),'text':tx(p),'heading':tx(heading) if heading else '',
                       'locator':f'{p.name}[{i}]','links':[linked_name(a) for a in p.find_all('a') if linked_name(a)]})
    info={}
    infobox=soup.select_one('#infoboxtable')
    if infobox:
        for row in infobox.find_all('tr'):
            cs=cells(row)
            if len(cs)==2 and cs[0].get('id')=='infoboxsection':
                info[tx(cs[0]).rstrip(':')]= {'value':tx(cs[1]),'quote':tx(row),'locator':'#infoboxtable/field['+tx(cs[0])+']'}
    kind='crop' if 'Seed' in info and 'Growth Time' in info else 'seed' if 'Crop' in info else 'equipment' if 'Ingredients' in info else 'reference'
    return {'schema':SCHEMA,'page_id':page,'source_id':sid,'source':source,'type':kind,'infobox':info,
            'sections':sections,'tables':parsed,'text_blocks':blocks,'occurrences':occurrences,
            'parse_status':'PARSED','limitations':['Decorative/unknown assets are recorded but not aligned.','Game version not inferred from revision.']}

def extract_structural(bundle,assets,aliases=None):
    page=bundle['page_id'];source=bundle['source'];sid=bundle['source_id'];info=bundle['infobox'];aliases=aliases or {}
    g={k:[] for k in ('entities','facts','relations','evidence','assets','occurrences','regions','observations','alignments')}
    nodes={};evs={};facts={};rels={};anchors=[]
    def node(name,kind='Item',**meta):
        eid=entity_id(name)
        if eid not in nodes:nodes[eid]={'id':eid,'name':name.replace('_',' '),'type':kind,'aliases':aliases.get(name,[]),'page_ids':[page],**meta}
        elif kind!='Item':nodes[eid]['type']=kind;nodes[eid].update(meta)
        return eid
    def evidence(quote,locator):
        e={'id':ident('evidence',sid,locator,quote),'source_id':sid,'page_id':page,'revision_id':source['revision_id'],
           'url':source.get('permanent_url',source['url']),'raw_path':source['raw_path'],'source_sha256':source['sha256'],
           'quote':quote,'quote_sha256':digest(quote.encode()),'locator':locator,'review_status':'candidate'}
        evs[e['id']]=e;return e['id']
    def fact(sub,pred,value,unit,ev,conditions=None,method='table_structure'):
        cond={'knowledge_scope':'frozen_wiki','game_version':'unverified',**(conditions or {})}
        f={'id':ident('fact',sub,pred,value,unit,cond),'subject':sub,'predicate':pred,'value':value,'unit':unit,
           'conditions':cond,'evidence_ids':[ev],'review_status':'candidate','method':method,'critical':True,'answer_allowed':False}
        facts[f['id']]=f;return f['id']
    def edge(s,p,o,ev,conditions=None):
        r=relation(s,p,o,[ev],conditions);rels[r['id']]=r;return r['id']
    main=node(page,{'crop':'Crop','seed':'Seed','equipment':'Equipment'}.get(bundle['type'],'Item'))
    for label,pred,unit in [('Growth Time','growth_days','growth_nights'),('Season','season','season'),('Crop','grows_into','entity'),('General Store','buy_price','g')]:
        if label not in info:continue
        row=info[label];val=row['value'];ev=evidence(row['quote'],row['locator'])
        if pred=='growth_days':
            m=re.search(r'(\d+)\s*days?',val,re.I)
            if not m:continue
            val=int(m.group(1))
        elif pred=='season':val=re.findall(r'Spring|Summer|Fall|Winter',val)
        elif pred=='grows_into':val=node(val,'Crop');edge(main,'GROWS_INTO',val,ev)
        elif pred=='buy_price':
            values=re.findall(r'([\d,]+)g',val)
            if not values:continue
            val=int(values[-1].replace(',',''))
        fact(main,pred,val,unit,ev)
        if pred=='season':
            for season in val:edge(main,'GROWS_IN_SEASON',node(season,'Season'),ev)
    intro=' '.join(b['text'] for b in bundle['text_blocks'] if not b['heading'])
    cat=re.search(r'\bis a (fruit|vegetable) crop\b',intro,re.I)
    if cat:
        ev=evidence(cat.group(), 'intro/category');fact(main,'category',cat.group(1).lower(),'category',ev,'text' if False else None,method='text_pattern')
        edge(main,'INSTANCE_OF',node(cat.group(1).title(),'Category'),ev)
    for t in bundle['tables']:
        rr=t['rows']
        if not rr:continue
        headers=[c['text'] for c in rr[0]]
        if headers and headers[0].endswith('Crops Bundle'):
            # This table template states explicit slots and item rows, including n-of-k.
            requirements=[];slots=sum(1 for row in rr for c in row for u in c['image_urls'] if u.endswith('/Bundle_Slot.png'))
            for row in rr[1:]:
                if not row or row[0]['text'].startswith('Reward:'):continue
                item_cell=next((c for c in row if c['links'] and any(l['name'] not in ('Spring','Summer','Fall','Winter','Crops') for l in c['links']) and not c['text'].endswith('Crops')),None)
                if item_cell is None:continue
                links=[l for l in item_cell['links'] if l['name'] not in ('Spring','Summer','Fall','Winter','Crops')]
                if len({l['name'] for l in links})!=1:continue
                name=links[0]['name'];match=re.search(r'\((\d+)\)',item_cell['text'])
                qty=int(match.group(1)) if match else 1;quality='gold' if any('Gold quality' in c['text'] for c in row) else 'normal'
                requirements.append({'item':name,'quantity':qty,'quality':quality})
            if slots and requirements and slots<=len(requirements):
                bid=node(headers[0].replace(' ','_'),'Bundle');ev=evidence(t['text'],t['locator'])
                fact(bid,'requirements',requirements,'requirements',ev);fact(bid,'choose_k',slots,'requirements',ev)
                for req in requirements:edge(node(req['item']),'BUNDLE_REQUIREMENT',bid,ev,{'quantity':req['quantity'],'quality':req['quality']})
        # Base sell prices: use the labelled Base column, never a hard-coded table index.
        if headers==['Sell Prices']:
            for j,row in enumerate(rr):
                labels=[c['text'] for c in row]
                if 'Base' in labels and j+1<len(rr):
                    col=labels.index('Base');cell=rr[j+1][col]
                    prices=[int(v.replace(',','')) for v in re.findall(r'([\d,]+)g',cell['text'])]
                    if len(prices)==4:
                        ev=evidence(cell['text'],cell['locator'])
                        for q,v in zip(('normal','silver','gold','iridium'),prices):fact(main,'sell_'+q,v,'g',ev,{'quality':q,'profession':'none'})
        if headers and headers[0]=='Stage 1':
            owner_name=info['Crop']['value'].replace(' ','_') if bundle['type']=='seed' else page
            owner=node(owner_name,'Crop')
            seq=[];dur=[]
            for row in rr[1:]:
                values=[c['text'] for c in row]
                if values and all(re.fullmatch(r'\d+ days?',v,re.I) for v in values[:sum(h.startswith('Stage') for h in headers)]):
                    dur=[int(re.match(r'\d+',v).group()) for v in values if re.fullmatch(r'\d+ days?',v,re.I)];break
            if not dur:continue
            ev=evidence(t['text'],t['locator']);rule_version=digest(dur)[:8]
            fact(owner,'stage_durations',dur,'growth_nights',ev)
            for k,h in enumerate(headers):
                if not (h.startswith('Stage') or h=='Harvest'):continue
                duration=dur[k] if k<len(dur) else 0
                stage=node(owner_name+'@'+rule_version+':stage:'+str(k+1),'CropStage',crop_id=owner,ordinal=k+1)
                seq.append(stage);edge(owner,'HAS_STAGE',stage,ev,{'ordinal':k+1});fact(stage,'duration',duration,'growth_nights',ev)
                if len(seq)>1:edge(seq[-2],'NEXT_STAGE',stage,ev,{'sequence_basis':'explicit_stage_headers','rule_version':rule_version})
                for occ in bundle['occurrences']:
                    if occ['table_index']==t['index'] and occ['cell_index']==k and occ.get('asset_id'):
                        anchors.append({'occurrence_id':occ['id'],'target_id':stage,'target_kind':'state','evidence_id':ev,'role':'state_depiction'})
            reg=re.search(r'Regrowth:\s*(\d+)',t['text'])
            if reg:fact(owner,'regrowth',int(reg.group(1)),'growth_nights',ev)
        # Equipment input/product tables: preserve typed, directed recipe semantics.
        if 'Ingredient' in headers and 'Name' in headers:
            for row in rr[1:]:
                if len(row)<len(headers):continue
                prod=row[headers.index('Name')];ing=row[headers.index('Ingredient')]
                if not prod['text'] or not ing['text']:continue
                ev=evidence(' '.join(c['text'] for c in row),t['locator']+'/'+prod['locator'].split('/')[-2])
                product=node(re.sub(r'\s*\(\d+\)$','',prod['text']).replace(' ','_'),'Product')
                recipe=node(page+':recipe:'+prod['text'],'Recipe')
                edge(recipe,'USES_EQUIPMENT',main,ev);edge(recipe,'PRODUCES',product,ev)
                for link in ing['links']:
                    input_id=node(link['name'],'Category' if link['name'] in ('Fruit','Vegetables') else 'Item')
                    rid=edge(recipe,'CONSUMES',input_id,ev)
                    for occ in bundle['occurrences']:
                        if occ['table_index']==t['index'] and occ['row_index']==rr.index(row) and occ.get('asset_id'):
                            anchors.append({'occurrence_id':occ['id'],'target_id':rid,'target_kind':'relation','evidence_id':ev,'role':'relation_illustration'})
    # Generic depiction anchors are based on the individual linked cell, not page title.
    for occ in bundle['occurrences']:
        if not occ.get('asset_id'):continue
        target=occ.get('linked_name')
        if not target and entity_id(occ['file_name_candidate']) in nodes:target=occ['file_name_candidate']
        if not target:continue
        eid=node(target)
        ev=evidence(occ['near_text'] or occ['alt'],occ['locator'])
        if not any(a['occurrence_id']==occ['id'] and a['target_kind']=='state' for a in anchors):
            anchors.append({'occurrence_id':occ['id'],'target_id':eid,'target_kind':'entity','evidence_id':ev,'role':'entity_depiction'})
    used={o['asset_id'] for o in bundle['occurrences'] if o['asset_id']}
    g.update(entities=list(nodes.values()),facts=list(facts.values()),relations=list(rels.values()),evidence=list(evs.values()),
             assets=[a for a in assets if a['id'] in used],occurrences=bundle['occurrences'],anchors=anchors,
             page_id=page,source=source,source_id=sid,text_extraction_mode='structural')
    return g
