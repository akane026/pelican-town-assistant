"""Render validated tool values by capability, without choosing a business workflow."""
import re
from collections import defaultdict
from .core import ValidationError,canonical

QUALITY={'normal':'普通','silver':'银星','gold':'金星','iridium':'铱星'}
SEASONS={'Spring':'春季','Summer':'夏季','Fall':'秋季','Winter':'冬季'}
INPUT_LABELS={'entity_id':'物品或作物身份','product_id':'希望比较的加工产物','quantity':'数量','quality':'品质',
    'profession':'职业情况','day':'游戏日期','season':'季节','watered':'浇水情况','acceleration':'生长加速情况',
    'inventory':'实际库存','completed':'已经完成的收集要求','user_level':'相关技能等级','stage':'作物生长阶段',
    'elapsed_in_stage':'当前阶段已过的有效生长夜晚','plan_option':'要采用的预留方案'}

def clarification_text(task,missing_fields):
    """Render the actual missing-input contract, never a model's invented default."""
    fields=list(dict.fromkeys(f for f in missing_fields if isinstance(f,str)))
    observed=[INPUT_LABELS[f] for f in fields if f in INPUT_LABELS]
    knowledge=[f for f in fields if f not in INPUT_LABELS]
    parts=[]
    if observed:parts.append('请补充或确认：'+'、'.join(observed)+'。已有输入会保留，未提供的条件不会自动取默认值。')
    if knowledge:parts.append('所需知识或能力尚未完整覆盖，需要先补齐可核验来源；直接提供一个数值不会自动使规则得到核实。')
    if not parts:parts.append('当前条件不足以给出所需结论，请在工作台补充必要信息。')
    parts.append('仅在已覆盖的知识与计算范围内继续；不承诺未支持的模组规则、限时排产或全局最优方案。')
    return '\n\n'.join(parts)

def visual_candidate_sections(receipts,entities,display_aliases=None):
    sections=[]
    for receipt in receipts.values():
        labels=[]
        for candidate in receipt['candidates']:
            eid=candidate['entity_id'];node=entities.get(eid,{})
            crop=node.get('crop_id',eid);base=entities.get(crop,node)
            aliases=(display_aliases or {}).get(crop.split(':',1)[-1],[])+base.get('aliases',[])
            label=next((a for a in aliases if re.search(r'[\u4e00-\u9fff]',a)),base.get('name',eid))
            if node.get('type')=='CropStage':label+=f"（阶段 {node['ordinal']} 候选）"
            labels.append(label)
        text='框选区域的候选为：'+'、'.join(labels)+'。' if labels else '当前框选区域没有可展示的匹配候选。'
        text+='这些是图像匹配候选，身份尚未确认；请在工作台确认或搜索其他物品。匹配距离不是概率，数量和品质没有从图片推断。'
        sections.append(text)
    return sections

def calculation_answer(calculations,entities,evidence,*,candidate,display_aliases=None):
    """No graph queries, model calls, prices, recipe constants or recomputation."""
    def name(eid):
        node=entities.get(eid,{})
        aliases=node.get('aliases',[])
        preferred=(display_aliases or {}).get(eid.split(':',1)[-1],[])
        aliases=[a for a in preferred if a in aliases]+aliases
        return next((x for x in aliases if re.search(r'[\u4e00-\u9fff]',x)),node.get('name',eid.split(':',1)[-1]))
    def stock_text(stock):
        pieces=[]
        for item,qualities in stock.items():
            desc='、'.join(f'{QUALITY.get(q,q)} {n} 个' for q,n in qualities.items() if n)
            pieces.append(name('entity:'+item)+'：'+(desc or '各品质均无剩余'))
        return '；'.join(pieces) or '已提供的库存列表为空'
    paragraphs=['候选诊断，知识与规则尚未完成人工审核。' if candidate else '以下结果来自当前任务绑定的已审核知识与规则。']
    comparisons=defaultdict(list)
    for calc in calculations.values():
        p=calc['user_inputs'];out=calc['outputs'];eid=p['entity_id'];label=name(eid);rule=calc['rule_id']
        if rule=='sale_value':
            paragraphs.append(f"直接出售｜{label}，{QUALITY[p['quality']]}，{out['quantity']} 个：单价 {out['unit_value_g']}g，合计 {out['sales_g']}g。")
        elif rule=='processing_value':
            product=name(p['product_id'])
            paragraphs.append(f"加工比较｜{p['quantity']} 个{QUALITY[p['quality']]}{label} → {product}：产物单价 {out['unit_value_g']}g，最终销售额 {out['sales_g']}g；直接出售原料为 {out['raw_opportunity_cost_g']}g，价值差额 {out['incremental_value_g']}g。不包含完成期限或排产承诺。")
            key=canonical([ {k:p.get(k) for k in ('entity_id','quantity','quality','profession','plan_option')},calc.get('plan_context'),calc.get('task_revision'),calc.get('snapshot_id')])
            comparisons[key].append((product,out['sales_g']))
        elif rule=='growth_timing':
            season=SEASONS.get(out['season'],out['season'])
            paragraphs.append(f"首次成熟｜{label}：需要 {out['effective_growth_nights']} 个有效生长夜晚。种植日加生长夜晚的结果为{season}第 {out['first_harvest_day']} 日；"+('可在本季首次成熟。' if out['within_season'] else '已超过本季范围，本季不能首次成熟。')+'条件为每日浇水、无生长加速。')
        elif rule=='stage_remaining':
            low,high=out['remaining_growth_nights'];interval=f'{low}' if low==high else f'{low}—{high}'
            paragraphs.append(f"阶段估计｜{label}，已确认阶段 {out['stage']}：还需 {interval} 个有效生长夜晚。条件为每日浇水、无生长加速；区间没有被当成精确日期。")
        elif rule=='crafting_gap':
            missing='；'.join(f'{name("entity:"+item)} {n} 个' for item,n in out['missing_materials'].items())
            paragraphs.append(f"制作检查｜{label}：材料缺口为{missing}。是否满足本工具已检查的材料与等级条件："+('是。' if out['can_craft'] else '否。'))
        elif rule=='bundle_reserve':
            if not out['options']:paragraphs.append(f'预留计划｜{label}：已提供的库存无法完成所需预留，不能按预留成功计算剩余可卖量。')
            for index,option in enumerate(out['options']):
                paragraphs.append(f'预留计划 {chr(65+index)}｜{label}\n预留：{stock_text(option["reserved"])}。\n该计划剩余：{stock_text(option["remaining"])}。')
            paragraphs.append('这些是独立比较的计划副本，原库存没有扣减，献祭没有被视为已在游戏中完成。')
        else:raise ValidationError('NO_OUTPUT_RENDERER:'+rule)
    for options in comparisons.values():
        if len({x[0] for x in options})>1:
            maximum=max(x[1] for x in options);winners=sorted({x[0] for x in options if x[1]==maximum})
            paragraphs.append('在以上已计算的同数量加工方案中，'+'、'.join(winners)+'的最终销售额'+('并列最高。' if len(winners)>1 else '最高。')+'每个方案单独使用同一份原料比较，不表示可以同时执行。')
    paragraphs.append('本回答只覆盖以上实际计算的结果。')
    refs={i for c in calculations.values() for k in ('used_fact_ids','used_relation_ids') for i in c.get(k,[]) if i in evidence}
    return {'answer_text':'\n\n'.join(paragraphs),'claim_evidence_refs':sorted(refs),'calculation_trace_refs':list(calculations),
            'unsupported_parts':[],'response_origin':'deterministic_calculation_projection/v1',
            'coverage':'actual_executed_calculations_only','human_approval':False}

def composite_answer(calculations,entities,evidence,checked_sections,goal_coverage,*,candidate,display_aliases=None,visual_receipts=None):
    """Keep verified explanations alongside projected calculations and omissions."""
    if calculations:
        answer=calculation_answer(calculations,entities,evidence,candidate=candidate,display_aliases=display_aliases)
        paragraphs=[answer['answer_text'].removesuffix('\n\n本回答只覆盖以上实际计算的结果。')]
    else:
        answer={'claim_evidence_refs':[],'calculation_trace_refs':[],'human_approval':False}
        paragraphs=['候选诊断，知识与规则尚未完成人工审核。' if candidate else '以下说明依据当前任务的已审核证据。']
    visual_receipts=visual_receipts or {}
    paragraphs.extend(visual_candidate_sections(visual_receipts,entities,display_aliases))
    for section in checked_sections:paragraphs.append(section['text'])
    refs=set(answer['claim_evidence_refs'])|{r for s in checked_sections for r in s['evidence_refs']}
    missing=[g for g in goal_coverage['goals'] if g['status']!='SATISFIED']
    if missing:
        kinds={'knowledge':'知识问题','explanation':'解释依据','calculation':'计算目标','comparison':'完整方案比较','identification':'对象确认','visual_candidates':'图像候选检索'}
        paragraphs.append('尚未完成：'+'、'.join(dict.fromkeys(kinds[g['kind']] for g in missing))+'。当前结果仅为部分结果，详细缺口见目标覆盖记录。')
    elif not goal_coverage['complete']:paragraphs.append('尚未登记完整目标，本次只展示已取得的结果，不能判定整题完成。')
    else:paragraphs.append('已覆盖本轮登记的目标；原文理解与整题完整性仍需独立样例评测。')
    answer.update(answer_text='\n\n'.join(paragraphs),claim_evidence_refs=sorted(refs),knowledge_sections=checked_sections,visual_trace_refs=list(visual_receipts),
                  unsupported_parts=[{'goal_id':g['goal_id'],'reason':g['reason']} for g in missing],
                  response_origin='evidence_checked_composite/v1',goal_coverage=goal_coverage)
    return answer
