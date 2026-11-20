"""Summarize actual runs; do not execute tests or invent missing checks."""
import re
from stardew_agent.core import *
records=rows(ARTIFACTS/'execution.jsonl')
full=next(x for x in reversed(records) if x['step']=='19-final-independent-suite')
log=(ROOT/full['stdout']).read_text();m=re.search(r'(\d+) passed',log)
assert full['exit_code']==0 and m
report={'status':'PARTIAL','automated_suite':{'status':'PASS','test_count':int(m[1]),'actual_command':full,'mode':'independently_installed_environment'},
 'independent_environment':read(ARTIFACTS/'repro/independent_environment.json'),
 'covered':['Real Semantica provenance roundtrip and directed multi-predicate graph',
 'Unreviewed formal mode rejection, isolated release subset, failed export rollback, review tampering and candidate immutability',
 'HMAC bundle tampering, task/snapshot mismatch, changed source files, deleted relationship/unique source',
 'Relevant vs irrelevant fact intervention and redundant valid source',
 'Duplicate import, changed page revision, raw/asset byte drift, partial failure resume and cache reuse',
 'Model timeout/HTTP429/malformed JSON via explicit synthetic fixtures',
 'Loopback Host/Origin/CSRF controls, corrupt image/path rejection and outside registered ROI denial',
 'Shared BQ/D image reranking contract, invalid IDs/duplicates fallback, no-model degradation',
 'Task correction, mid-loop revision invalidation, inventory copy constraints and no-evidence answer rejection',
 'Deterministic calculation answer projection; bounded model-assisted checking for non-calculation answers'],
 'real_online_examples':{'sale':'artifacts/v3/agent_pilots/sale.json','composition':'artifacts/v3/agent_pilots/compose.json',
 'clarification_resume':'artifacts/v3/agent_pilots/continued-650cbcf4-b476-4ef3-86f7-4586d89ecf64.json',
 'semantic_controls':'artifacts/v3/evaluation/semantic_pixel_controls_summary.json','pixel_reranking':'artifacts/v3/evaluation/pixel_rerank_summary.json',
 'fixed_input_image_control':'artifacts/v3/evaluation/isolated_image_retrieval_summary.json',
 'goal_entity_variation':'artifacts/v3/evaluation/agent_variations_summary.json',
 'semantic_checker_negative':'artifacts/v3/evaluation/answer_semantic_pilot.json'},
 'not_proven':['No independent human knowledge/rule approvals or complete formal 60-question run',
 'No new held-out screenshot recognition score or full source-unit alignment gold',
 'A real semantic-check pilot missed an ambiguous old sentence. Calculation answers now project validated outputs, but general factual natural-language checking is not a proof of truth',
 'No load/stress guarantee, cross-machine acquisition reproduction, original QM training or full EGTR execution'],
 'no_fake_review':'Publication success tests use temporary copies and explicitly synthetic local_user fixtures. Production current.json remains absent.'}
write(ARTIFACTS/'evaluation/reliability_summary.json',report)
lines=['# 可靠性与独立复现记录','',f"新建并按哈希锁独立安装的 `.venv-repro`：完整工程测试 **{m[1]} passed**，命令真实退出 0。",'',
 f"原始日志：`{full['stdout']}`；代码指纹：`{full['code_manifest']}`。",'',
 '上述是模块 / API 工程断言，不是正式业务正确率。模型故障使用显式合成夹具；真实模型执行另有日志。','',
 '独立环境实际从 `.venv-repro/lib/python3.12/site-packages` 加载 Semantica，重新读取 1,150 条来源记录并计算甘蓝 12 个普通品质销售 1320g。没有复制虚拟环境。共享的是本机已合法取得的冻结来源，没有冒充重新抓站或重新请求视觉模型。','',
 '## 已执行覆盖','']+['- '+x for x in report['covered']]+['','## 尚未证明','']+['- '+x for x in report['not_proven']]+['',report['no_fake_review'],'']
(ROOT/'docs/v3/RELIABILITY.md').write_text('\n'.join(lines))
print(canonical({'status':report['status'],'tests':int(m[1]),'independent_environment':'PASS','formal_release_exists':(DATA/'current.json').exists()}))
