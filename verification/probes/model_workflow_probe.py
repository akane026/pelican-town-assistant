"""Live visual pilot and a real function-call -> local tool -> grounded answer roundtrip."""
import json
from verification.chatecnu import ChatECNU
from verification.common import BASE, DATA, dump, now, read_jsonl
from verification.pipeline import AssistantPipeline


def parse_json(text):
    try:return json.loads(text or '')
    except ValueError:return None


def run():
    api=ChatECNU();samples={r['sample_id']:r for r in read_jsonl(DATA/'visual_test_manifest.jsonl')}
    gallery=read_jsonl(DATA/'gallery.jsonl');labels=[r['entity'] for r in gallery if 'Quality_Icon' not in r['entity']]
    rows=[];selected=['V28','V30','V12','V13','V14','V18','V19','V27','V10','V11','V32','V33']
    # This is a second diagnostic method on the same published crops, not additional samples.
    for sid in selected:
        s=samples[sid];content=[{'type':'text','text':
            '识别这张星露谷物语局部截图。可用实体 ID 为 '+json.dumps(labels)+'。只输出 JSON：'
            '{"entity":一个 ID 或 null,"candidates":[最多三个 ID],"needs_confirmation":true 或 false}。'
            '图库外对象用 null，不能硬选；不确定生长阶段请保留多个候选。只看像素，不猜数量或品质。'},api.image_content(BASE/s['path'])]
        result=api.call(api.config['CHATECNU_VISION_MODEL'],[{'role':'user','content':content}],label='visual-pilot:'+sid,
                        response_format={'type':'json_object'})
        parsed=parse_json(result.get('content'));valid=bool(parsed is not None and isinstance(parsed.get('candidates'),list) and type(parsed.get('needs_confirmation'))==bool
            and parsed.get('entity') in [None]+labels and all(c in labels for c in parsed.get('candidates',[])) and len(parsed.get('candidates',[]))<=3)
        row={'sample_id':sid,'response':result,'parsed':parsed,'valid_schema':valid,
             'unknown':s['unknown'],'labels':s['labels'],'selection':'preselected representative diagnostic subset'}
        rows.append(row);dump(BASE/'results/model_visual_pilot.json',{'status':'RUNNING','rows':rows})
        print(sid,result['status'],parsed,flush=True)
        if result.get('http_status') in (401,403,429):return 2
    known=[r for r in rows if not r['unknown']];unknown=[r for r in rows if r['unknown']]
    metrics={'known_n':len(known),'unknown_n':len(unknown),
      'known_top1':sum(r['valid_schema'] and r['parsed']['entity'] in r['labels'] for r in known),
      'known_top3':sum(r['valid_schema'] and bool(set(r['labels']) & ({r['parsed']['entity']}|set(r['parsed']['candidates']))) for r in known),
      'unknown_not_auto_accepted':sum(r['valid_schema'] and (r['parsed']['entity'] is None or r['parsed']['needs_confirmation']) for r in unknown),
      'schema_valid':sum(r['valid_schema'] for r in rows)}
    dump(BASE/'results/model_visual_pilot.json',{'status':'EXECUTED','rows':rows,'metrics':metrics,
        'limitations':['mixed dev/test representative subset','no reference-gallery images supplied, ID list only','human label review pending','not a population accuracy estimate']})
    schema={'type':'object','properties':{'day':{'type':'integer'},'plants':{'type':'integer'},'season':{'type':'string','enum':['Spring']},'watered':{'type':'boolean'}},
            'required':['day','plants','season','watered'],'additionalProperties':False}
    messages=[{'role':'system','content':'你是游戏助手。图像模块已确认 Parsnip_Seeds；所有计算必须调用 planting 工具，不能自己补数字。'},
              {'role':'user','content':'春23日，我要买种子种50株防风草，每天浇水，无加速，按普通品质出售。何时成熟，收益多少？'}]
    first=api.call(api.config['CHATECNU_MODEL'],messages,label='workflow:tool_request',tools=[{'type':'function','function':{'name':'planting','description':'确定性种植计算','parameters':schema}}],
                   tool_choice={'type':'function','function':{'name':'planting'}})
    workflow={'at':now(),'tool_request':first,'status':'FAIL'}
    try:
        tc=first['tool_calls'][0];args=json.loads(tc['function']['arguments'])
        if tc['function']['name']!='planting' or args!={'day':23,'plants':50,'season':'Spring','watered':True}:raise ValueError('Wrong tool args')
        s=samples['V28'];request={'image_path':s['path'],'image_sha256':s['sha256'],'kind':'item','intent':'planting',
                                'question':messages[1]['content'],'state':args}
        tool=AssistantPipeline().run(request)
        if tool['status']!='OK':raise ValueError('Local tool failed')
        payload={k:tool[k] for k in ['status','result','evidence_ids','citations']}
        messages += [{'role':'assistant','content':first.get('content') or '', 'tool_calls':first['tool_calls']},
                     {'role':'tool','tool_call_id':tc['id'],'name':'planting','content':json.dumps(payload,ensure_ascii=False)},
                     {'role':'user','content':'根据工具结果输出 JSON，包含 answer（中文答案），numeric_result（原样保留 result），used_evidence_ids（实际引用的 evidence_ids）。说明只扣种子成本、每天浇水、无加速、普通品质。'}]
        final=api.call(api.config['CHATECNU_MODEL'],messages,label='workflow:grounded_answer',response_format={'type':'json_object'})
        parsed=parse_json(final.get('content'))
        passed=bool(parsed and parsed.get('numeric_result')==tool['result'] and set(parsed.get('used_evidence_ids',[]))<=set(tool['evidence_ids']) and parsed.get('used_evidence_ids'))
        workflow.update(status='PASS' if passed else 'FAIL',validated_tool_args=args,tool_output=payload,answer_response=final)
    except (ValueError,KeyError,TypeError,IndexError) as exc:workflow['reason']=type(exc).__name__
    dump(BASE/'results/model_workflow.json',workflow)
    print('WORKFLOW',workflow['status'],flush=True);return int(workflow['status']!='PASS')


if __name__=='__main__':raise SystemExit(run())
