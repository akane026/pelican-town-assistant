"""Masked template baseline: no gold, OCR, model or screenshot labels at runtime."""
import time
from pathlib import Path
import numpy as np
from PIL import Image
from .common import BASE, DATA, dump, file_sha, jsonl, load, read_jsonl

DEFAULT_CONFIG={'method':'masked_rgb_template/v1','accepted_error_max':0.13,'minimum_gap':0.025,
                'scales':[0.52,0.64,0.76,0.88,1.0],'stride':2,'max_crop_dimension':72}


class VisualRetriever:
    def __init__(self,config=None):
        self.config=config or DEFAULT_CONFIG;self.gallery=read_jsonl(DATA/'gallery.jsonl');self.templates=[]
        for r in self.gallery:
            if 'Quality_Icon' in r['entity']:continue
            path=BASE/r['path']
            if file_sha(path)!=r['sha256']:raise ValueError('Corrupt gallery asset')
            im=Image.open(path).convert('RGBA');box=im.getchannel('A').getbbox()
            if box:im=im.crop(box)
            self.templates.append((r,im))

    def candidates(self,path,kind='item'):
        start=time.perf_counter();image=Image.open(path).convert('RGB');image.thumbnail((72,72))
        src=np.asarray(image,dtype=np.float32);h,w=src.shape[:2];rank=[]
        for record,template in self.templates:
            if ('_Stage_' in record['entity'])!=(kind=='stage'):continue
            best=float('inf');best_box=None
            for scale in self.config['scales']:
                factor=min(w/template.width,h/template.height)*scale
                tw=max(3,round(template.width*factor));th=max(3,round(template.height*factor))
                if tw>w or th>h:continue
                target=np.asarray(template.resize((tw,th),Image.Resampling.NEAREST),dtype=np.float32)
                mask=target[:,:,3]>128
                if mask.sum()<5:continue
                positions=[(y,x) for y in range(0,h-th+1,self.config['stride']) for x in range(0,w-tw+1,self.config['stride'])]
                for y,x in positions:
                    observed=src[y:y+th,x:x+tw]
                    error=float(np.abs(observed[mask]-target[:,:,:3][mask]).mean()/255)
                    if error<best:best=error;best_box=[x,y,tw,th]
            rank.append({'entity':record['entity'],'image_id':record['image_id'],'distance':round(best,6),'bbox_resized':best_box,
                         'occurrence_ids':record['occurrence_ids'][:4]})
        rank.sort(key=lambda r:r['distance']);top=rank[:3]
        gap=rank[1]['distance']-rank[0]['distance'] if len(rank)>1 else 0
        accepted=bool(top and top[0]['distance']<=self.config['accepted_error_max'] and gap>=self.config['minimum_gap'])
        if top and top[0]['entity'] in ['Pink_Wine','Pink_Jelly']:accepted=False
        return {'candidates':top,'status':'AUTO_ACCEPT' if accepted else 'NEEDS_CONFIRMATION' if top and top[0]['distance']<0.25 else 'UNKNOWN',
                'score_is_probability':False,'gap':round(gap,6),'latency_ms':round((time.perf_counter()-start)*1000,2),
                'kind_supplied_by_input':kind,'method':self.config['method']}


def probe():
    rows=read_jsonl(DATA/'visual_test_manifest.jsonl');v=VisualRetriever();pred=[]
    sources={r['capture_id']:r for r in read_jsonl(DATA/'external_screenshot_manifest.jsonl')}
    for sample in rows:
        if file_sha(BASE/sample['path'])!=sample['sha256']:raise ValueError('Corrupt input crop')
        source=sources[sample['capture_id']]
        if file_sha(BASE/source['path'])!=sample['source_sha256']:raise ValueError('Corrupt original screenshot')
    # Evaluate dev first. Thresholds are predeclared; no test-driven threshold tuning.
    config={**DEFAULT_CONFIG,'manifest_sha256':file_sha(DATA/'visual_test_manifest.jsonl'),'frozen_before_test':True,'dev_tuning':'none; conservative predefined thresholds'}
    dump(DATA/'visual_config.json',config)
    for split in ['dev','test']:
        for sample in [r for r in rows if r['split']==split]:
            p=v.candidates(BASE/sample['path'],sample['kind']);p.update(sample_id=sample['sample_id'],split=split)
            pred.append(p);print(sample['sample_id'],p['status'],p['candidates'][0]['entity'],flush=True)
    jsonl(BASE/'results/visual_predictions.jsonl',pred)
    metrics={}
    for split in ['dev','test']:
        group=[(r,next(p for p in pred if p['sample_id']==r['sample_id'])) for r in rows if r['split']==split]
        known=[x for x in group if not x[0]['unknown']];unknown=[x for x in group if x[0]['unknown']]
        accepted=[x for x in group if x[1]['status']=='AUTO_ACCEPT']
        metrics[split]={'total':len(group),'known':len(known),'unknown':len(unknown),
          'top1_hits':sum(p['candidates'][0]['entity'] in r['labels'] for r,p in known),
          'top3_hits':sum(bool(set(r['labels'])&{c['entity'] for c in p['candidates']}) for r,p in known),
          'known_auto_accepted':sum(p['status']=='AUTO_ACCEPT' for r,p in known),
          'unknown_rejected':sum(p['status']!='AUTO_ACCEPT' for r,p in unknown),
          'auto_accept_errors':sum(p['candidates'][0]['entity'] not in r['labels'] for r,p in accepted),
          'auto_accept_count':len(accepted),'latency_median_ms':float(np.median([p['latency_ms'] for r,p in group])),
          'latency_p95_ms':float(np.percentile([p['latency_ms'] for r,p in group],95)),
          'by_kind':{kind:{'n':sum(r['kind']==kind for r,p in known),'top3':sum(r['kind']==kind and bool(set(r['labels'])&{c['entity'] for c in p['candidates']}) for r,p in known)} for kind in ['item','stage']}}
    result={'status':'PARTIAL','pilot_metrics':metrics,'planned_48_sample_gate':'NOT_MET',
       'limitations':['35 crops, not 48','Only three known stage crops','Independent label review pending','Game versions and mods unverified','Collection-menu crops are separate from inventory','Quantity and quality recognition not implemented','Two test stage negatives have provisional species labels; report conservative metric excluding them too'],
       'config_sha256':file_sha(DATA/'visual_config.json'),'external_encoder':'NOT_RUN; template baseline first'}
    conservative=[(r,next(p for p in pred if p['sample_id']==r['sample_id'])) for r in rows if r['split']=='test' and r['unknown'] and r['sample_id'] not in ['V34','V35']]
    result['conservative_unknown_metric']={'excluded_ids':['V34','V35'],'reason':'crop species labels provisional; kept in full pilot table, excluded from this secondary estimate',
      'unknown_n':len(conservative),'not_auto_accepted':sum(p['status']!='AUTO_ACCEPT' for r,p in conservative)}
    dump(BASE/'results/visual_metrics.json',result);print(metrics);return 2

if __name__=='__main__':raise SystemExit(probe())
