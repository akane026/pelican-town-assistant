from __future__ import annotations
import time,io
import numpy as np
from PIL import Image
from .core import *
from verification.vision import DEFAULT_CONFIG

class ImageStore:
    def upload(self,data,task_id):
        if len(data)>10_000_000:raise ValidationError('UPLOAD_LIMIT')
        try:
            with Image.open(io.BytesIO(data)) as im:
                if im.width*im.height>20_000_000:raise ValidationError('IMAGE_TOO_LARGE')
                im.load();rgb=im.convert('RGBA');h=digest(data);p=DATA/'uploads'/task_id/(h+'.png');p.parent.mkdir(parents=True,exist_ok=True);rgb.save(p)
        except (OSError,Image.DecompressionBombError) as e:raise ValidationError('INVALID_IMAGE') from e
        rec={'image_id':ident('upload',task_id,h),'task_id':task_id,'path':str(p.relative_to(ROOT)),'sha256':file_hash(p),'width':rgb.width,'height':rgb.height,'shared_knowledge':False}
        write(DATA/'uploads/registry'/(rec['image_id'].split(':')[1]+'.json'),rec);return rec
    def get(self,image_id,task_id):
        if not image_id.startswith('upload:') or len(image_id)!=35 or any(c not in '0123456789abcdef' for c in image_id[7:]):raise ValidationError('INVALID_IMAGE_ID')
        r=read(DATA/'uploads/registry'/(image_id.split(':')[1]+'.json'))
        if r['task_id']!=task_id:raise ValidationError('IMAGE_TASK_MISMATCH')
        if file_hash(ROOT/r['path'])!=r['sha256']:raise ValidationError('UPLOAD_CHANGED')
        return r
    def region(self,image_id,task_id,box):
        validate_bbox(box);r=self.get(image_id,task_id);rid=ident('user_region',image_id,box,'v1')
        with Image.open(ROOT/r['path']) as im:
            xy=[int(box[0]*im.width),int(box[1]*im.height),int(box[2]*im.width),int(box[3]*im.height)]
            if xy[2]<=xy[0] or xy[3]<=xy[1]:raise ValidationError('EMPTY_REGION')
            p=DATA/'uploads'/task_id/(rid.split(':')[1]+'.png');im.crop(xy).save(p)
        return {'region_id':rid,'image_id':image_id,'bbox':box,'path':str(p.relative_to(ROOT)),'sha256':file_hash(p),'task_id':task_id}

class VisualMatcher:
    def __init__(self,snapshot,config=None):
        self.s=snapshot;self.config=dict(config or DEFAULT_CONFIG);self.gallery={}
        for a in snapshot.domain['alignments']:
            if a['target_kind'] not in ('entity','state') or a['status']!='matched':continue
            target=snapshot.records['entities'][a['target_id']]
            for rid in a['region_ids']:
                region=snapshot.records['regions'][rid];asset=snapshot.records['assets'][region['asset_id']]
                path=ROOT/asset['path']
                if file_hash(path)!=asset['sha256']:raise ValidationError('GALLERY_ASSET_CHANGED')
                with Image.open(path) as source:
                    source=source.convert('RGBA');box=region.get('bbox',[0,0,1,1]);validate_bbox(box)
                    template=source.crop((int(box[0]*source.width),int(box[1]*source.height),int(box[2]*source.width),int(box[3]*source.height)))
                    alpha=template.getchannel('A').getbbox()
                    if not alpha:continue
                    template=template.crop(alpha)
                # Shared pixels remain ambiguous across both assets and contexts.
                key=digest([template.size,digest(template.tobytes())])
                row=self.gallery.setdefault(key,{'asset':asset,'template':template,'targets':{}})
                previous=row['targets'].get(target['id'])
                entry={'entity':target,'alignment_id':a['id'],'region_id':rid,'asset_id':asset['id'],
                       'confirmation_level':a.get('confirmation_level','legacy_candidate'),
                       'review_status':a.get('review_status','candidate')}
                if previous is None or entry['review_status']=='approved_human':row['targets'][target['id']]=entry
    def match(self,path,kind='item'):
        if kind not in ('item','stage'):raise ValidationError('UNKNOWN_VISION_KIND')
        t=time.perf_counter();im=Image.open(path).convert('RGB');im.thumbnail((72,72));arr=np.asarray(im,dtype=np.float32);h,w=arr.shape[:2];rank=[]
        for row in self.gallery.values():
            targets=[x for x in row['targets'].values() if (x['entity']['type']=='CropStage')==(kind=='stage')]
            if not targets:continue
            template=row['template'];best=float('inf')
            for scale in self.config['scales']:
                factor=min(w/template.width,h/template.height)*scale;tw=max(3,round(template.width*factor));th=max(3,round(template.height*factor))
                if tw>w or th>h:continue
                target=np.asarray(template.resize((tw,th),Image.Resampling.NEAREST),dtype=np.float32);mask=target[:,:,3]>128
                if mask.sum()<5:continue
                for y in range(0,h-th+1,2):
                    for x in range(0,w-tw+1,2):best=min(best,float(np.abs(arr[y:y+th,x:x+tw][mask]-target[:,:,:3][mask]).mean()/255))
            for target in targets:rank.append({'entity_id':target['entity']['id'],'name':target['entity']['name'],'distance':round(best,6),
                      'asset_id':target['asset_id'],'region_id':target['region_id'],'alignment_id':target['alignment_id'],
                      'confirmation_level':target['confirmation_level'],'review_status':target['review_status'],'shared_pixels':len(row['targets'])>1})
        rank.sort(key=lambda x:(x['distance'],x['entity_id']));unique={}
        for r in rank:unique.setdefault(r['entity_id'],r)
        top=list(unique.values())[:3];gap=top[1]['distance']-top[0]['distance'] if len(top)>1 else 0
        threshold_pass=bool(top and kind=='item' and top[0]['distance']<=self.config['accepted_error_max'] and gap>=self.config['minimum_gap'] and not top[0]['shared_pixels'])
        return {'candidates':top,'status':'NEEDS_CONFIRMATION' if top and top[0]['distance']<.25 else 'UNKNOWN',
                'threshold_pass':threshold_pass,'automatic_identity_confirmation':False,'calibration_status':'PENDING_INDEPENDENT_REVIEW',
                'gallery_pixels':len(self.gallery),'gap':round(gap,6),
                'snapshot_id':self.s.id,'method':'region_aware_masked_template/v3.2','score_is_probability':False,
                'quantity':'not_inferred','quality':'not_inferred','elapsed_seconds':time.perf_counter()-t,'limitations':['Thresholds are inherited diagnostics, not probabilities or formal calibration.','Identity requires user confirmation; shared pixels do not determine a unique entity.']}
