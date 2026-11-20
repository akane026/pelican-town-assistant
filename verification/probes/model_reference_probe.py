"""Second, explicitly post-pilot diagnostic: nearest-neighbor enlarged crops plus reference images."""
import json
from PIL import Image
from verification.common import BASE, DATA, dump, load, read_jsonl
from verification.chatecnu import ChatECNU
from verification.probes.model_workflow_probe import parse_json


def main():
    api=ChatECNU();prior=load(BASE/'results/model_visual_pilot.json');rows=[]
    samples={r['sample_id']:r for r in read_jsonl(DATA/'visual_test_manifest.jsonl')}
    predicted={r['sample_id']:r for r in read_jsonl(BASE/'results/visual_predictions.jsonl')}
    gallery={r['entity']:r for r in read_jsonl(DATA/'gallery.jsonl')}
    out=BASE/'data/model_preview';out.mkdir(parents=True,exist_ok=True)
    def enlarge(path,label):
        im=Image.open(path).convert('RGBA');factor=max(1,240//max(im.size));im=im.resize((im.width*factor,im.height*factor),Image.Resampling.NEAREST)
        dest=out/(label+'.png');im.save(dest);return dest
    for item in prior['rows']:
        sid=item['sample_id'];s=samples[sid];candidates=predicted[sid]['candidates'];ids=[c['entity'] for c in candidates]
        content=[{'type':'text','text':'比较第一张待识别截图与后面的三个 Wiki 参考图。背景、像素缩放和数字覆盖可能不同；请匹配整个物体，不能只匹配其中几片叶子。若三个都不对请返回 null。只输出 JSON {"entity":候选 ID 或 null,"needs_confirmation":布尔值}。'},
                 {'type':'text','text':'待识别截图：'},api.image_content(enlarge(BASE/s['path'],sid+'-query'))]
        for c in candidates:
            content += [{'type':'text','text':'候选 ID：'+c['entity']},api.image_content(enlarge(BASE/gallery[c['entity']]['path'],c['entity']))]
        r=api.call(api.config['CHATECNU_VISION_MODEL'],[{'role':'user','content':content}],label='reference-pilot:'+sid,response_format={'type':'json_object'})
        parsed=parse_json(r.get('content'));valid=bool(parsed is not None and parsed.get('entity') in ids+[None] and type(parsed.get('needs_confirmation'))==bool)
        rows.append({'sample_id':sid,'response':r,'parsed':parsed,'valid_schema':valid,'labels':s['labels'],'unknown':s['unknown'],'candidate_ids':ids})
        dump(BASE/'results/model_reference_pilot.json',{'status':'RUNNING','rows':rows})
        print(sid,r['status'],parsed,flush=True)
        if r.get('http_status') in (401,403,429):return 2
    known=[r for r in rows if not r['unknown']];unknown=[r for r in rows if r['unknown']]
    metrics={'known_n':len(known),'unknown_n':len(unknown),'known_top1':sum(r['valid_schema'] and r['parsed']['entity'] in r['labels'] for r in known),
             'unknown_not_auto_accepted':sum(r['valid_schema'] and (r['parsed']['entity'] is None or r['parsed']['needs_confirmation']) for r in unknown),
             'schema_valid':sum(r['valid_schema'] for r in rows)}
    dump(BASE/'results/model_reference_pilot.json',{'status':'EXECUTED','metrics':metrics,'rows':rows,
      'scope':'post-test diagnostic on same 12 images; references AND nearest-neighbor enlargement changed; not a controlled single-factor ablation'})
    print(metrics);return 0

if __name__=='__main__':raise SystemExit(main())
