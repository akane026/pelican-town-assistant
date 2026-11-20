"""Create a small read-only source/image review packet; never approve anything."""
import argparse,base64,html,io,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image,ImageDraw
from stardew_agent.core import ROOT,ARTIFACTS,read,write,canonical
from stardew_agent.knowledge import Snapshot,review_export
from stardew_agent.rules import RULES,rule_audit,rule_fingerprint

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--snapshot',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();snapshot=Snapshot(args.snapshot,allow_candidate=True);out=Path(args.output)
    if out.exists():raise ValueError('REVIEW_OUTPUT_ALREADY_EXISTS')
    out.mkdir(parents=True);review_export(snapshot.id)
    selected=[]
    for predicate in ('sell_normal','category','value_formula','equipment','stage_durations','requirements'):
        matches=[r for r in snapshot.domain['facts'] if r['predicate']==predicate]
        if matches:selected.append(matches[0])
    selected += [r for r in snapshot.domain['relations'] if r.get('support_fact_ids')][:2]
    methods={}
    for row in snapshot.domain['alignments']:methods.setdefault((row['method'],row.get('confirmation_level')),[]).append(row)
    for group in methods.values():selected+=group[:2]
    rows=[];cards=[];md=['# 待人工核对：核心图文与规则','',f'快照：`{snapshot.id}`','',
        '状态：PENDING_HUMAN。本页仅展示代表性记录；不等于全库审核，也不包含默认批准。请在本机工作台逐条提交真实审核理由。','']
    for number,row in enumerate(selected,1):
        evidence=[snapshot.records['evidence'][eid] for eid in row.get('evidence_ids',[])]
        pictures=[];tags=[]
        for rid in row.get('region_ids',[])[:2]:
            region=snapshot.records['regions'][rid];asset=snapshot.records['assets'][region['asset_id']]
            with Image.open(ROOT/asset['path']) as source:
                source=source.convert('RGBA');box=region['bbox'];xy=[int(box[0]*source.width),int(box[1]*source.height),int(box[2]*source.width),int(box[3]*source.height)]
                original=source.copy();ImageDraw.Draw(original).rectangle(xy,outline='#c95534',width=max(1,source.width//100))
                roi=source.crop(xy)
                for label,picture in [('原图与区域',original),('区域实际像素',roi)]:
                    filename=f'{number}-{len(pictures)}.png';picture.save(out/filename);pictures.append(filename)
                    stream=io.BytesIO();picture.save(stream,format='PNG');url='data:image/png;base64,'+base64.b64encode(stream.getvalue()).decode()
                    tags.append(f'<figure><img src="{url}"><figcaption>{label}</figcaption></figure>')
        excerpts=[{'id':e['id'],'page_id':e['page_id'],'quote_excerpt':' '.join(e['quote'].split()[:24]),'url':e['url'],
            'locator':e['locator'],'raw_path':e['raw_path'],'source_sha256':e['source_sha256']} for e in evidence[:3]]
        item={'record':row,'sources':excerpts,'images':pictures,'human_action':None};rows.append(item)
        title=row.get('target_id') or ' / '.join(str(row.get(k,'')) for k in ('subject','predicate','value','object'))
        md += [f'## {number}. {title}','',f'记录 `{row["id"]}`；审核状态 `{row.get("review_status")}`；视觉等级 `{row.get("confirmation_level","不适用")}`。','']
        for e in excerpts:md += [f'- [{e["page_id"]}：{e["locator"]}]({e["url"]}) — {e["quote_excerpt"]}']
        for filename in pictures:md += ['',f'![图文核对]({(out/filename).resolve()})']
        cards.append('<article><h2>'+html.escape(title)+'</h2><p>'+html.escape(row['id'])+'</p><div class="images">'+''.join(tags)+'</div>'+''.join('<blockquote>'+html.escape(e['quote_excerpt'])+' <a href="'+html.escape(e['url'],quote=True)+'">'+html.escape(e['page_id'])+'</a></blockquote>' for e in excerpts)+'<details><summary>条件、依赖与来源字段</summary><pre>'+html.escape(canonical(item))+'</pre></details></article>')
    rules=[{**r,'fingerprint':rule_fingerprint(rid),'actual_review':rule_audit(rid)} for rid,r in RULES.items()]
    write(out/'records.json',{'snapshot_id':snapshot.id,'status':'PENDING_HUMAN','representative_records':rows,'rules':rules,'full_queue':str(ARTIFACTS/'review'/snapshot.id/'queue.json')})
    (out/'待审证据清单.md').write_text('\n'.join(md),encoding='utf-8')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>鹈鹕镇·图文审核证据</title><style>body{font:16px system-ui;background:#f2f5e9;color:#283d32;max-width:1100px;margin:40px auto;padding:0 20px}article{background:white;padding:24px;border-radius:12px;margin:18px 0}h2{font-size:19px;overflow-wrap:anywhere}.images{display:flex;gap:24px}img{image-rendering:pixelated;max-width:350px;max-height:180px;min-height:50px}pre{white-space:pre-wrap;overflow-wrap:anywhere}blockquote{border-left:3px solid #b7c8a5;margin:14px 0;padding-left:14px}</style><h1>核心图文待审清单</h1><p>只读证据材料 · PENDING_HUMAN · '+snapshot.id+'</p><p>自动检查与模型核验均不代表人工批准；关键知识、规则、评测参考答案分别审核。</p>'+''.join(cards),encoding='utf-8')
    print(canonical({'status':'PENDING_HUMAN','snapshot_id':snapshot.id,'records':len(rows),'output':str(out)}));return 2

if __name__=='__main__':raise SystemExit(main())
