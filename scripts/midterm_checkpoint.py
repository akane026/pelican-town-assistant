"""Freeze an honest intermediate handoff; does not mark unfinished acceptance passed."""
from collections import Counter
from stardew_agent.core import *
from stardew_agent.knowledge import Snapshot,review_export

s=Snapshot(allow_candidate=True);d=ROOT/'docs/v3';baseline=ROOT/read(ARTIFACTS/'baseline_pointer.json')['directory'];manifest=read(baseline/'manifest.json')
changed=[p for p,v in manifest['original_files'].items() if not (ROOT/p).exists() or file_hash(ROOT/p)!=v['sha256']]
write(ARTIFACTS/'baseline_integrity_final.json',{'status':'PASS' if not changed else 'FAIL','original_files':len(manifest['original_files']),'changed':changed,'archive_hash_matches':file_hash(baseline/'original.tar.gz')==manifest['archive_sha256']})
write(ARTIFACTS/'roundtrip_final.json',s.roundtrip());review_export(s.id)
tests=read(ARTIFACTS/'evaluation/reliability_summary.json')['automated_suite']['test_count']
statuses=['PASS','PASS','PARTIAL','PASS','PASS','PASS','PARTIAL','PASS','PARTIAL','PASS','PARTIAL','PARTIAL','PARTIAL','PARTIAL','PARTIAL','PARTIAL','PARTIAL','BLOCKED','PARTIAL','PARTIAL']
limits=[
 '旧离线复跑为 PARTIAL / 2；原文件保留且哈希不变。',
 '仅固定原函数组件执行；非原版 EGTR / QM 全流程。',
 '数据契约与协议已有；独立标注金标准未完成。',
 '24页分段与真实图像资源；准确性仍需人工核对。',
 'A/B 同模板新作物导入；没有逐作物业务分支。',
 '真实模型像素抽取含3个复合图对象；非全面视觉准确率。',
 '实体、状态、关系说明候选已产生；实际错图/缺图/去上下文小样运行，独立人审不足。',
 'Semantica 构图、导出、来源存取和独立进程重载运行。',
 '审核完整性、子集发布、失败回滚在临时副本测试通过；无人审签字，没有正式快照。',
 'A/B冻结导入；重复幂等、页修订、原文/像素变更、失败恢复和缓存复用测试通过。',
 '同文本消融、来源单位与语义干预小样已运行；人工评分未完成。',
 '实体/关系/子图、签名包、补查与真实问题像素重排已运行；独立效果评测不足。',
 '六类纯计算与相关/无关事实、关键边、唯一/冗余来源干预测试通过；规则人审待补。',
 '局部候选与版本状态已实现；全交互和新截图效果未正式评测。',
 '真实销售、组合与多轮改目标/实体运行；计算答案直接由工具输出生成，普通知识问答仍需独立语义评测。',
 '审阅/搜索/上传框选/补参历史经浏览器验证；全部交互覆盖未完成。',
 '72条词项诊断BQ/D持平；6次联合图像重排另列，未宣称独立盲测优势。',
 '60题候选参考答案与来源目录已保存；0题人审、8题缺独立图片，正式执行BLOCKED。',
 f'{tests}项工程测试在独立安装环境通过，1150来源与代表计算复现；全面效果/安全保证不成立。',
 '中期验收状态与证据已归档；整体 V3 最终验收未完成。']
records=rows(ARTIFACTS/'execution.jsonl');tasks=[]
for i,(status,lim) in enumerate(zip(statuses,limits),1):
 matching=[r for r in records if str(r['step']).startswith(f'{i:02d}') or (i in (13,14,15) and str(r['step']).startswith('12-15')) or (i in (6,7,8) and str(r['step']).startswith('06-08')) or (i in (12,17) and str(r['step']).startswith('12-17'))]
 tasks.append({'step':i,'status':status,'limitations':[lim],'command_records':matching,'test_result':'See linked actual stdout; absent command mapping is not counted as an independent step run.'})
write(d/'TASKS.json',tasks)
criteria=[
('PASS','原始归档、哈希复核','baseline_integrity_final.json'),('PASS','原版组件/适配边界','upstream/component_run.json'),
('PARTIAL','分段与图像定位已实现，语义人审待补','evaluation/construction_source_units.json'),('PASS','A/B真实同模板页面','freeze/batch_b_result.json'),
('PASS','请求含真实像素与区域','evaluation/compound_summary.json'),('PARTIAL','实体候选与实际错图降级；独立真值待审','evaluation/semantic_pixel_controls_summary.json'),
('PARTIAL','阶段/持续规则分开，视觉真值待审','evaluation/construction_cases.json'),('PARTIAL','真实复合图关系说明候选，效果未评分','evaluation/compound_summary.json'),
('PASS','原始资源与派生裁剪字段分开','acquisition/compound_images.json'),('PASS','实际Semantica来源与多模态对象','roundtrip_final.json'),
('PASS','方向/多谓词测试通过','execution.jsonl'),('PARTIAL','正式模式拦截、发布完整性测试通过；实际人审待补','review/'+s.id+'/compact.json'),
('PASS','两批导入、重复幂等、页变更与失败恢复','freeze/batch_b_result.json'),('PASS','图像/上下文键与实际资产变化隔离测试','execution.jsonl'),
('PARTIAL','K0/K1同文本产物，金标准待审','evaluation/construction_summary.json'),('PASS','真实实体/关系/任务子图输出','evaluation/retrieval_rows.json'),
('PARTIAL','6次联合重排及4次固定文本换图干预，独立图像效果待审','evaluation/isolated_image_retrieval_summary.json'),('PASS','计算无图句柄，补查显式记账','execution.jsonl'),
('PASS','相关/无关事实、删关键边、唯一/冗余来源隔离干预','execution.jsonl'),('PASS','用户输入/证据/计算来源分别保存','agent_pilots/sale.json'),
('PASS','真实动态工具组合及多轮目标/实体切换；不代表全题正确率','evaluation/agent_variations_summary.json'),('PASS','澄清后真实续答959g；旧证据被拒后重新检索','agent_pilots/continued-650cbcf4-b476-4ef3-86f7-4586d89ecf64.json'),
('PASS','预留后9个/315g且不改原库存；新回答直接呈现工具值','agent_pilots/compose.json'),
('PARTIAL','候选API和纠正入口；新截图校准待补','ui/review.jpg'),('PASS','原图/原文/区域/来源可查看','ui/review.jpg'),
('PARTIAL','真实工作台/框选/历史续答已验证；全部操作待补','ui/clarification_resume.jpg'),('PARTIAL','共享预算开发诊断；完整基线和Agent对照待补','evaluation/retrieval_summary.json'),
('BLOCKED','60题候选已有，独立人审与8道视觉输入缺失','evaluation/formal_summary.json'),('PARTIAL','错误和API边界测试；不宣称全面安全保证','evaluation/reliability_summary.json'),
('PASS','哈希锁独立安装，1150来源重载与甘蓝计算复现','repro/independent_environment.json')]
lines=['# V3 中期阶段交付（非最终验收）','','用户最新要求：先收束工程，再用指定guizang PPT skill重制汇报。工程在本检查点停止扩展；保留未完成项，不伪造正式通过。','',f'候选快照：`{s.id}`。正式发布快照：无。',
 '',f'当前统计：24 页、88 个独立图像、165 个领域实体、192 条事实、218 条关系、705 条来源证据、740 条候选图文关联。{tests} 项工程测试在独立环境通过。',
 '', '真实 Agent：甘蓝12个普通品质1320g；补参后7个银星959g；新组合任务预留后9个防风草315g，答案直接由工具值生成。另一个真实两轮任务从甜瓜果酒/果酱1500g/1100g切换到土豆直卖/腌菜240g/630g，旧结果失效。旧歧义句和模型语义检查漏检作为负例保留；没有宣称模型审查等于真值。',
 '', '12题 × 6种检索共72条词项开发诊断：BQ/D初次证据完整度均4/12，逐题持平。补查后可计算均12/12，不是人工任务正确率。另有6次联合重排及4次固定文本/候选换图干预；后者仅替换像素时前两条证据随甘蓝/大蒜改变，不是独立截图准确率。',
 '', '## A01—A30 当前状态','','| ID | 状态 | 证据与限制 | 原始产物 |','|---|---|---|---|']
for i,(status,reason,path) in enumerate(criteria,1):lines.append(f'| A{i:02d} | {status} | {reason} | [{path}](../../artifacts/v3/{path}) |')
lines+=['','## 每步命令、退出码与限制','','全部命令以 `artifacts/v3/execution.jsonl` 为准；每条含命令 argv、工作目录、退出码、用时与 stdout/stderr 文件。早期直接调用的产物不能冒充独立 shell 步骤；步骤01独立复跑命令存于基线 manifest。','',
 '| 步骤 | 状态 | 已记录运行 | 限制 |','|---|---|---|---|']
for t in tasks:
 refs='；'.join(f"{r['step']} / exit {r['exit_code']}" for r in t['command_records']) or '依赖产物/源码见 TASKS.json；没有独立命令证据不算另一次运行'
 lines.append(f"| {t['step']:02d} | {t['status']} | {refs} | {t['limitations'][0]} |")
lines+=['','## 操作与下一步','','启动和已实现命令见根目录 README。模型只接既有 ChatECNU；没有加载新本地大型模型。已保留原资料、旧核验和失败结果。',
 '', '优先继续：人工审核精简清单和规则 → 来源侧独立图文标注及截图划分 → 冻结正式金标准并执行60题。继续检验普通知识问答的语义支持和跨任务稳定性；模型语义检查已发生漏检，不能视作正确率证明。增量/干预/独立环境已执行。',
 '', 'AI使用说明：模型辅助编码、候选抽取与工具调度；没有模型代签人审。上下文与计算验证、来源记录和负结果分别保留。']
(d/'DELIVERY.md').write_text('\n'.join(lines)+'\n')
# Compact human list: pixels, ambiguity/rejection, directional illustration, then numerical facts.
selected=[a for a in s.domain['alignments'] if a['method']=='compound_mllm_alignment/v1'][:9]
selected += [next(a for a in s.domain['alignments'] if a['target_kind']=='state')]
selected += [next(f for f in s.domain['facts'] if f['subject']=='entity:Kale' and f['predicate']=='sell_normal')]
review=['# 精简图文待审清单','',f'快照 `{s.id}`。以下均待用户审核；自动 matched 不是人审通过。','',
 '在工作台“建库审阅”中可搜索 ID，查看原图、区域坐标、完整原文与模型理由，输入审核依据后决定批准/拒绝/保留。','']
for i,r in enumerate(selected,1):
 review += [f'## {i}. {r.get("target_id",r.get("subject"))}',f'记录：`{r["id"]}`；自动状态：{r.get("status","candidate")}；方法：{r.get("method")}', '']
 assets={s.records['regions'][rid]['asset_id'] for rid in r.get('region_ids',[])}
 for aid in sorted(assets):
  a=s.records['assets'][aid];review.append(f'![原始 Wiki 图像]({ROOT/a["path"]})')
 if r.get('region_ids'):review.append('区域：'+canonical([s.records['regions'][rid]['bbox'] for rid in r['region_ids']]))
 review.append(r.get('reason_summary',f"候选值：{r.get('value')} {r.get('unit')}"))
 for eid in r['evidence_ids'][:1]:
  e=s.records['evidence'][eid];review += ['',f'来源：[ {e["page_id"]} / {e["revision_id"]} ]({e["url"]})；定位 `{e["locator"]}`。',f'> {e["quote"][:700]}']
 review+=['','用户结论：待填写；依据：待填写。','']
(d/'REVIEW_CHECKLIST.md').write_text('\n'.join(review)+'\n')
(ROOT/'PROJECT_STATE.md').write_text(f'# 项目状态\n\n用户最新指示：先收束工程，随后安装指定guizang PPT skill并重制汇报。\n\n当前为可运行候选原型，V3整体PARTIAL。详细20步及A01—A30见 docs/v3/DELIVERY.md 与 TASKS.json。\n\n24页、88个图像、真实像素建图、Semantica来源、6类候选计算、动态单Agent及本机工作台已运行。独立安装环境中{tests}项工程测试通过。原核验哈希复核PASS。\n\n新完成：增量与失败恢复、证据因果干预、原子发布临时副本测试、独立环境复现、60题待审目录、真实换图/缺图/去上下文、6次问题与像素联合重排。真实澄清续答959g；新组合预留315g答案直接由工具输出生成；旧模型语义漏检保留为负例。\n\n关键知识/规则人审、独立图像效果与正式60题执行尚未完成；没有正式发布快照。不得用{tests}项测试或图像小样冒充业务正确率。\n\n没有后台长期运行目标。保留全部负结果，旧G0/ITER1建议不作为执行证明。\n')
write(ARTIFACTS/'midterm_checkpoint.json',{'status':'PARTIAL','snapshot_id':s.id,'baseline_unchanged':not changed,'acceptance_counts':dict(Counter(x[0] for x in criteria)),
    'test_count':tests,'checkpoint_reason':'continued engineering reached sufficient midterm evidence; human gold and formal evaluation remain pending','at':now()})
print(canonical(read(ARTIFACTS/'midterm_checkpoint.json')))
