"""Frozen new-page development diagnostic; never a blind test or human approval."""
from __future__ import annotations
import argparse, io, re, sys, time
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bs4 import BeautifulSoup
from PIL import Image
from stardew_agent.core import ROOT, DATA, ARTIFACTS, now, digest, file_hash, read, write, ValidationError
from stardew_agent.parsing import parse_page, extract_structural, norm_url
from stardew_agent.construction import enrich_text, derive_graph
from stardew_agent.visual import extract_visual, align_graph
from stardew_agent.normalization import normalize_graph
from stardew_agent.knowledge import build_snapshot, Snapshot
from stardew_agent.knowledge_quality import audit_graph
from verification.acquire import Fetcher

PAGES=['Radish','Radish_Seeds']
OWNED=['core.py','parsing.py','construction.py','visual.py','normalization.py','knowledge_quality.py','capabilities.py','knowledge.py','model.py']


def freeze(run):
    if (run/'protocol.json').exists():return read(run/'protocol.json')
    protocol={'schema':'new-page-diagnostic/v1','frozen_at':now(),'pages':PAGES,
        'classification':'ASSISTANT_DEVELOPMENT_DIAGNOSTIC_NOT_BLIND','human_gold':'PENDING',
        'selection':'Two previously absent public Wiki pages, chosen before parser/model execution. Assistant has inspected their public text.',
        'code_hashes':{name:file_hash(ROOT/'stardew_agent'/name) for name in OWNED},
        'script_hash':file_hash(__file__),
        'asset_selection':'Only original article image URLs whose normalized filename starts Radish; deduplicate bytes; original sprites, not real game screenshots.',
        'model_budget':{'visual_assets':4,'text_pages':2,'alignment_pages':2,'retries':0},
        'expected_structure':{'crop':'entity:Radish','seed':'entity:Radish_Seeds','growth_days':6,'season':['Summer'],
            'sell_normal':90,'stage_durations':[2,1,2,1],'crop_stages':5,'next_stage_edges':4,'seed_relation':'GROWS_INTO'},
        'evaluation_layers':['source byte/revision/asset freeze','generic text/table extraction','actual pixel observations and object ROI',
            'structural vs model alignment levels','normalization/dependency validation','Semantica graph/provenance roundtrip'],
        'criteria':['No page-specific parser branches or model-name inference as visual proof.',
            'Each model-confirmed match names real object ROIs; conflicting/ambiguous outputs stay unapproved.',
            'Expected numeric values are predeclared assistant checks, never model-derived gold.',
            'Successful transport/schema validation is not visual accuracy; report failures separately.',
            'No activation, release, baseline-manifest change, or automatic human decision.'],
        'limitations':['Selected public sprites do not measure game screenshot recognition.','Two related pages cannot establish general corpus accuracy.',
            'Public text was visible during protocol drafting; this is a development diagnostic.']}
    write(run/'protocol.json',protocol)
    (run/'PROTOCOL.md').write_text('# 新页面开发诊断协议\n\n这是助手开发诊断，不是盲测或独立金标准。页面选择与期望值在通用解析和模型调用前冻结。公开文本已被助手看过。\n\n'
        '输入：Radish、Radish Seeds 官方 Wiki 原始 HTML 与其萝卜相关原始精灵图；不冒充真实游戏截图。\n\n'
        '分层核验：来源/像素哈希 → 通用文本/表格抽取 → 实际像素观测和对象 ROI → 语义确认等级与条件 → 规范化/依赖检查 → Semantica 构图、来源与独立读取。\n\n'
        '预声明结构检查：6 生长夜、夏季、普通品质基础售价 90g、阶段时长 [2,1,2,1]、5 个阶段、4 条 NEXT_STAGE、种子 GROWS_INTO 作物。价格和天数只能来自文本证据。\n\n'
        '最多 4 次视觉观测、2 次文本抽取、2 次对齐；不重试失败输出，不重置调用额度。全部模型结果保持候选。逐条记录失败与未确认对齐，生成真实图文审阅材料，由人另行审核。\n\n'
        '原快照、原配置与 latest/current 指针不改；新数据和日志独立保存。详细冻结代码哈希与预算见 protocol.json。\n')
    return protocol


def check_code(protocol):
    changed=[name for name,value in protocol['code_hashes'].items() if file_hash(ROOT/'stardew_agent'/name)!=value]
    if changed:raise ValidationError('FROZEN_CODE_CHANGED:'+','.join(changed))
    if file_hash(__file__)!=protocol['script_hash']:raise ValidationError('FROZEN_SCRIPT_CHANGED')


def acquire(run):
    fetch=Fetcher();sources=[];image_urls=[];assets={}
    try:
        for page in PAGES:
            response=fetch.get('https://stardewvalleywiki.com/'+page);content=response.content;html=response.text
            revision=re.search(r'"wgRevisionId"\s*:\s*(\d+)',html) or re.search(r'[?&]oldid=(\d+)',html)
            if not revision:raise ValidationError('SOURCE_REVISION_MISSING:'+page)
            raw=run/'raw'/(page+'-'+digest(content)[:12]+'.html');raw.parent.mkdir(parents=True,exist_ok=True);raw.write_bytes(content)
            sources.append({'page_id':page,'url':'https://stardewvalleywiki.com/'+page,'permanent_url':'https://stardewvalleywiki.com/mediawiki/index.php?title='+page+'&oldid='+revision.group(1),
                'revision_id':revision.group(1),'sha256':digest(content),'raw_path':str(raw.relative_to(ROOT)),'retrieved_at':now(),
                'split':'assistant_development_diagnostic','game_version_assertion':'unverified','http_status':response.status_code})
            soup=BeautifulSoup(html,'lxml');body=soup.select_one('.mw-parser-output')
            if body is None:raise ValidationError('ARTICLE_BODY_MISSING')
            for image in body.select('img[src]'):
                url=norm_url(image['src']);name=unquote(Path(urlparse(url).path).name)
                if urlparse(url).hostname=='stardewvalleywiki.com' and name.startswith('Radish') and url not in image_urls:image_urls.append(url)
            write(run/'sources.json',sources);print('ACQUIRED_PAGE',page,'revision',revision.group(1),flush=True)
        for url in image_urls:
            response=fetch.get(url);content=response.content;image=Image.open(io.BytesIO(content));image.load()
            checksum=digest(content);path=run/'assets'/(checksum+'.'+image.format.lower());path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
            aid='asset:'+checksum
            if aid in assets:assets[aid].setdefault('url_aliases',[]).append(url);continue
            assets[aid]={'id':aid,'url':url,'sha256':checksum,'pixel_sha256':digest(image.convert('RGBA').tobytes()),'path':str(path.relative_to(ROOT)),
                'width':image.width,'height':image.height,'format':image.format,'source_kind':'original_wiki_sprite','retrieved_at':now(),
                'license_status':'per_asset_review_pending','split':'assistant_development_diagnostic'}
            write(run/'assets.json',list(assets.values()));print('ACQUIRED_ASSET',unquote(Path(urlparse(url).path).name),image.size,flush=True)
    finally:write(run/'acquisition.json',{'events':fetch.events,'sources':len(sources),'assets':len(assets),'blocked':fetch.blocked})
    return sources,list(assets.values())


def pipeline(run,protocol):
    sources=read(run/'sources.json');assets=read(run/'assets.json')
    from stardew_agent.model import ModelClient
    model=ModelClient();documents=[];cache={};model_calls=[]
    preferred=['Radish.png','Radish_Seeds.png','Radish_Stage_1.png','Radish_Stage_5.png']
    chosen=[a['id'] for name in preferred for a in assets if unquote(Path(urlparse(a['url']).path).name)==name][:4]
    write(run/'visual_selection.json',{'asset_ids':chosen,'rule':preferred,'actual_pixel_inputs':True,'real_game_screenshots':False})
    for source in sources:
        bundle=parse_page(source,assets);graph=extract_structural(bundle,assets)
        page=run/'pages'/source['page_id'];write(page/'source_bundle.json',bundle);write(page/'structural_graph.json',graph)
        graph=enrich_text(graph,bundle,model);write(page/'text_graph.json',graph)
        print('TEXT',source['page_id'],graph.get('text_model_log'),flush=True)
        for asset in graph['assets']:
            if asset['id'] not in cache:
                observation,regions=extract_visual(asset,model if asset['id'] in chosen else None)
                cache[asset['id']]=(observation,regions)
                print('VISUAL',Path(urlparse(asset['url']).path).name,observation['method'],observation.get('model_error'),flush=True)
            observation,regions=cache[asset['id']];graph['observations'].append(observation);graph['regions'].extend(regions)
        graph['alignments']=align_graph(graph,graph['observations'],graph['regions'],model)
        write(page/'fused_document_graph.json',graph);documents.append(graph)
        print('ALIGNED',source['page_id'],len(graph['alignments']),graph.get('alignment_model_log'),flush=True)
    merged=derive_graph(documents);normalized=normalize_graph(merged);graph=normalized['graph']
    write(run/'normalization.json',normalized['migration']);write(run/'quality.json',audit_graph(graph));write(run/'fused_graph.json',graph)
    checks=[]
    def check(name,actual,expected):checks.append({'name':name,'actual':actual,'expected':expected,'status':'PASS' if actual==expected else 'FAIL','label_origin':'assistant_predeclared_not_human_gold'})
    for predicate in ('growth_days','season','sell_normal','stage_durations'):
        values=[f['value'] for f in graph['facts'] if f['subject']=='entity:Radish' and f['predicate']==predicate and f.get('method')!='llm_candidate']
        check(predicate,values,[protocol['expected_structure'][predicate]])
    check('crop_stages',len([e for e in graph['entities'] if e['type']=='CropStage' and e.get('crop_id')=='entity:Radish']),5)
    check('next_stage_edges',len([r for r in graph['relations'] if r['predicate']=='NEXT_STAGE']),4)
    check('seed_to_crop',any(r['subject']=='entity:Radish_Seeds' and r['predicate']=='GROWS_INTO' and r['object']=='entity:Radish' for r in graph['relations']),True)
    build_id='new-page-'+digest({'protocol':protocol,'sources':sources,'graph':graph})[:20]
    write(ARTIFACTS/'builds'/build_id/'fused_graph.json',graph)
    manifest=build_snapshot(build_id,activate=False)
    snapshot=Snapshot(manifest['snapshot_id'],allow_candidate=True);roundtrip=snapshot.roundtrip()
    review=[]
    for row in graph['alignments']:
        if row.get('confirmation_level') in ('visual_checked','model_unconfirmed'):
            review.append({'id':row['id'],'target_id':row['target_id'],'target_kind':row['target_kind'],'status':row['status'],
                'confirmation_level':row['confirmation_level'],'reason_summary':row['reason_summary'],
                'regions':[snapshot.records['regions'][r] for r in row['region_ids']],
                'evidence':[snapshot.records['evidence'][e] for e in row['evidence_ids']],
                'action':None,'actor':None,'reason':None})
    write(run/'review.json',{'snapshot_id':snapshot.id,'status':'PENDING_HUMAN','items':review})
    lines=['# 新页图文审阅清单','','自动匹配保持候选；以下没有人工批准。图像是 Wiki 精灵图。','']
    for row in review:
        lines += [f"## {row['target_kind']} · {row['target_id']}",'',f"状态：{row['status']} / {row['confirmation_level']}；对齐：`{row['id']}`",'',row['reason_summary'],'']
        for region in row['regions']:
            asset=snapshot.records['assets'][region['asset_id']]
            lines += [f"![原图]({ROOT/asset['path']})",f"![对象 ROI]({ROOT/region['path']})" if region.get('path') else '',f"区域：`{region['bbox']}`",'']
        for evidence in row['evidence']:lines += [f"来源：[{evidence['page_id']} / {evidence['revision_id']}]({evidence['url']})；{evidence['locator']}",evidence['quote'][:500],'']
    (run/'REVIEW.md').write_text('\n'.join(lines))
    summary={'status':'CANDIDATE_DIAGNOSTIC_COMPLETE','classification':protocol['classification'],'human_review':'PENDING','snapshot_id':snapshot.id,
        'build_id':build_id,'counts':{k:len(v) for k,v in snapshot.domain.items()},'structure_checks':checks,'roundtrip':roundtrip,
        'model_visual_assets':sum(o['method']=='ChatECNU_visual/v1' for o,_ in cache.values()),
        'visual_checked_alignments':sum(a.get('confirmation_level')=='visual_checked' for a in graph['alignments']),
        'model_failures':[{'asset_id':o['asset_id'],'error':o['model_error']} for o,_ in cache.values() if o.get('model_error')],
        'alignment_validation_errors':[e for d in documents for e in d.get('alignment_validation_errors',[])],
        'limitations':protocol['limitations']+['No human identity/ROI correctness score; model acceptance is not recognition accuracy.']}
    write(run/'result.json',summary);print('RESULT',summary,flush=True)
    return summary


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['freeze','acquire','run']);parser.add_argument('--run-dir',required=True)
    args=parser.parse_args();run=(ROOT/args.run_dir).resolve()
    if not run.is_relative_to(ROOT/'data/post_midterm'):raise ValidationError('RUN_DIRECTORY_OUTSIDE_POST_MIDTERM')
    run.mkdir(parents=True,exist_ok=True);protocol=freeze(run);check_code(protocol)
    started=now()
    try:
        if args.phase=='acquire':acquire(run)
        elif args.phase=='run':pipeline(run,protocol)
        else:print('FROZEN',str(run/'protocol.json'))
        return 0
    except Exception as exc:
        write(run/('failure-'+args.phase+'-'+digest(started)[:8]+'.json'),{'phase':args.phase,'at':started,'type':type(exc).__name__,'message':str(exc)})
        raise


if __name__=='__main__':raise SystemExit(main())
