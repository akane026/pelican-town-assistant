# V3 中期阶段交付（非最终验收）

用户最新要求：先收束工程，再用指定guizang PPT skill重制汇报。工程在本检查点停止扩展；保留未完成项，不伪造正式通过。

候选快照：`0f47248587aed45b1fc0887be608e3bd8ad429f79e363e841c4b828dcd7b2ac0`。正式发布快照：无。

当前统计：24 页、88 个独立图像、165 个领域实体、192 条事实、218 条关系、705 条来源证据、740 条候选图文关联。70 项工程测试在独立环境通过。

真实 Agent：甘蓝12个普通品质1320g；补参后7个银星959g；新组合任务预留后9个防风草315g，答案直接由工具值生成。另一个真实两轮任务从甜瓜果酒/果酱1500g/1100g切换到土豆直卖/腌菜240g/630g，旧结果失效。旧歧义句和模型语义检查漏检作为负例保留；没有宣称模型审查等于真值。

12题 × 6种检索共72条词项开发诊断：BQ/D初次证据完整度均4/12，逐题持平。补查后可计算均12/12，不是人工任务正确率。另有6次联合重排及4次固定文本/候选换图干预；后者仅替换像素时前两条证据随甘蓝/大蒜改变，不是独立截图准确率。

## A01—A30 当前状态

| ID | 状态 | 证据与限制 | 原始产物 |
|---|---|---|---|
| A01 | PASS | 原始归档、哈希复核 | [baseline_integrity_final.json](../../artifacts/v3/baseline_integrity_final.json) |
| A02 | PASS | 原版组件/适配边界 | [upstream/component_run.json](../../artifacts/v3/upstream/component_run.json) |
| A03 | PARTIAL | 分段与图像定位已实现，语义人审待补 | [evaluation/construction_source_units.json](../../artifacts/v3/evaluation/construction_source_units.json) |
| A04 | PASS | A/B真实同模板页面 | [freeze/batch_b_result.json](../../artifacts/v3/freeze/batch_b_result.json) |
| A05 | PASS | 请求含真实像素与区域 | [evaluation/compound_summary.json](../../artifacts/v3/evaluation/compound_summary.json) |
| A06 | PARTIAL | 实体候选与实际错图降级；独立真值待审 | [evaluation/semantic_pixel_controls_summary.json](../../artifacts/v3/evaluation/semantic_pixel_controls_summary.json) |
| A07 | PARTIAL | 阶段/持续规则分开，视觉真值待审 | [evaluation/construction_cases.json](../../artifacts/v3/evaluation/construction_cases.json) |
| A08 | PARTIAL | 真实复合图关系说明候选，效果未评分 | [evaluation/compound_summary.json](../../artifacts/v3/evaluation/compound_summary.json) |
| A09 | PASS | 原始资源与派生裁剪字段分开 | [acquisition/compound_images.json](../../artifacts/v3/acquisition/compound_images.json) |
| A10 | PASS | 实际Semantica来源与多模态对象 | [roundtrip_final.json](../../artifacts/v3/roundtrip_final.json) |
| A11 | PASS | 方向/多谓词测试通过 | [execution.jsonl](../../artifacts/v3/execution.jsonl) |
| A12 | PARTIAL | 正式模式拦截、发布完整性测试通过；实际人审待补 | [review/0f47248587aed45b1fc0887be608e3bd8ad429f79e363e841c4b828dcd7b2ac0/compact.json](../../artifacts/v3/review/0f47248587aed45b1fc0887be608e3bd8ad429f79e363e841c4b828dcd7b2ac0/compact.json) |
| A13 | PASS | 两批导入、重复幂等、页变更与失败恢复 | [freeze/batch_b_result.json](../../artifacts/v3/freeze/batch_b_result.json) |
| A14 | PASS | 图像/上下文键与实际资产变化隔离测试 | [execution.jsonl](../../artifacts/v3/execution.jsonl) |
| A15 | PARTIAL | K0/K1同文本产物，金标准待审 | [evaluation/construction_summary.json](../../artifacts/v3/evaluation/construction_summary.json) |
| A16 | PASS | 真实实体/关系/任务子图输出 | [evaluation/retrieval_rows.json](../../artifacts/v3/evaluation/retrieval_rows.json) |
| A17 | PARTIAL | 6次联合重排及4次固定文本换图干预，独立图像效果待审 | [evaluation/isolated_image_retrieval_summary.json](../../artifacts/v3/evaluation/isolated_image_retrieval_summary.json) |
| A18 | PASS | 计算无图句柄，补查显式记账 | [execution.jsonl](../../artifacts/v3/execution.jsonl) |
| A19 | PASS | 相关/无关事实、删关键边、唯一/冗余来源隔离干预 | [execution.jsonl](../../artifacts/v3/execution.jsonl) |
| A20 | PASS | 用户输入/证据/计算来源分别保存 | [agent_pilots/sale.json](../../artifacts/v3/agent_pilots/sale.json) |
| A21 | PASS | 真实动态工具组合及多轮目标/实体切换；不代表全题正确率 | [evaluation/agent_variations_summary.json](../../artifacts/v3/evaluation/agent_variations_summary.json) |
| A22 | PASS | 澄清后真实续答959g；旧证据被拒后重新检索 | [agent_pilots/continued-650cbcf4-b476-4ef3-86f7-4586d89ecf64.json](../../artifacts/v3/agent_pilots/continued-650cbcf4-b476-4ef3-86f7-4586d89ecf64.json) |
| A23 | PASS | 预留后9个/315g且不改原库存；新回答直接呈现工具值 | [agent_pilots/compose.json](../../artifacts/v3/agent_pilots/compose.json) |
| A24 | PARTIAL | 候选API和纠正入口；新截图校准待补 | [ui/review.jpg](../../artifacts/v3/ui/review.jpg) |
| A25 | PASS | 原图/原文/区域/来源可查看 | [ui/review.jpg](../../artifacts/v3/ui/review.jpg) |
| A26 | PARTIAL | 真实工作台/框选/历史续答已验证；全部操作待补 | [ui/clarification_resume.jpg](../../artifacts/v3/ui/clarification_resume.jpg) |
| A27 | PARTIAL | 共享预算开发诊断；完整基线和Agent对照待补 | [evaluation/retrieval_summary.json](../../artifacts/v3/evaluation/retrieval_summary.json) |
| A28 | BLOCKED | 60题候选已有，独立人审与8道视觉输入缺失 | [evaluation/formal_summary.json](../../artifacts/v3/evaluation/formal_summary.json) |
| A29 | PARTIAL | 错误和API边界测试；不宣称全面安全保证 | [evaluation/reliability_summary.json](../../artifacts/v3/evaluation/reliability_summary.json) |
| A30 | PASS | 哈希锁独立安装，1150来源重载与甘蓝计算复现 | [repro/independent_environment.json](../../artifacts/v3/repro/independent_environment.json) |

## 每步命令、退出码与限制

全部命令以 `artifacts/v3/execution.jsonl` 为准；每条含命令 argv、工作目录、退出码、用时与 stdout/stderr 文件。早期直接调用的产物不能冒充独立 shell 步骤；步骤01独立复跑命令存于基线 manifest。

| 步骤 | 状态 | 已记录运行 | 限制 |
|---|---|---|---|
| 01 | PASS | 01-record-baseline-commit / exit 0 | 旧离线复跑为 PARTIAL / 2；原文件保留且哈希不变。 |
| 02 | PASS | 02-07-original-components / exit 0 | 仅固定原函数组件执行；非原版 EGTR / QM 全流程。 |
| 03 | PARTIAL | 03-04-tests / exit 0 | 数据契约与协议已有；独立标注金标准未完成。 |
| 04 | PASS | 04-05 / exit 0 | 24页分段与真实图像资源；准确性仍需人工核对。 |
| 05 | PASS | 05-07 / exit 0；05-07-network / exit 0；05-bundle-template / exit 0 | A/B 同模板新作物导入；没有逐作物业务分支。 |
| 06 | PASS | 06-07-stage-pixels / exit 0；06-08-compound-pixels / exit 0 | 真实模型像素抽取含3个复合图对象；非全面视觉准确率。 |
| 07 | PARTIAL | 06-08-compound-pixels / exit 0 | 实体、状态、关系说明候选已产生；实际错图/缺图/去上下文小样运行，独立人审不足。 |
| 08 | PASS | 08-build / exit 0；08-roundtrip / exit 0；06-08-compound-pixels / exit 0；08-final-inspect / exit 0 | Semantica 构图、导出、来源存取和独立进程重载运行。 |
| 09 | PARTIAL | 09-tests / exit 0；09-publication-integrity / exit 0 | 审核完整性、子集发布、失败回滚在临时副本测试通过；无人审签字，没有正式快照。 |
| 10 | PASS | 10-batch-a-parse / exit 0；10-batch-a-visual / exit 0；10-batch-b-frozen / exit 0；10-merge-batches / exit 0；10-incremental-matrix / exit 0 | A/B冻结导入；重复幂等、页修订、原文/像素变更、失败恢复和缓存复用测试通过。 |
| 11 | PARTIAL | 11-construction-diagnostic / exit 2；11-semantic-pixel-controls / exit 0；11-nonempty-context-controls / exit 0 | 同文本消融、来源单位与语义干预小样已运行；人工评分未完成。 |
| 12 | PARTIAL | 12-15-tests / exit 0；12-pixel-rerank-contracts / exit 0；12-17-live-pixel-rerank / exit 0 | 实体/关系/子图、签名包、补查与真实问题像素重排已运行；独立效果评测不足。 |
| 13 | PARTIAL | 12-15-tests / exit 0 | 六类纯计算与相关/无关事实、关键边、唯一/冗余来源干预测试通过；规则人审待补。 |
| 14 | PARTIAL | 12-15-tests / exit 0 | 局部候选与版本状态已实现；全交互和新截图效果未正式评测。 |
| 15 | PARTIAL | 12-15-tests / exit 0；15-live-sale / exit 2；15-live-sale-retry / exit 0；15-live-compose / exit 2；15-live-compose-retry / exit 2；15-live-compose-resume / exit 2；15-live-clarification / exit 0；15-agent-summary / exit 2；15-finalization-tests / exit 0；15-live-compose-finalization / exit 1；15-live-compose-persistence-fix / exit 0；15-live-clarification-resume / exit 0；15-semantic-guard-contracts / exit 0；15-semantic-finalization-tests / exit 0；15-live-semantic-check-repair / exit 2；15-live-goal-entity-variation / exit 0；15-output-projection-tests / exit 0；15-live-structured-composition / exit 0；15-variation-arithmetic-audit / exit 0 | 真实销售、组合与多轮改目标/实体运行；计算答案直接由工具输出生成，普通知识问答仍需独立语义评测。 |
| 16 | PARTIAL | 16-runtime-tests / exit 0 | 审阅/搜索/上传框选/补参历史经浏览器验证；全部交互覆盖未完成。 |
| 17 | PARTIAL | 17-retrieval-diagnostic / exit 0；12-17-live-pixel-rerank / exit 0；17-isolated-image-control / exit 0 | 72条词项诊断BQ/D持平；6次联合图像重排另列，未宣称独立盲测优势。 |
| 18 | BLOCKED | 18-prepare-60-review / exit 0；18-formal-status / exit 2 | 60题候选参考答案与来源目录已保存；0题人审、8题缺独立图片，正式执行BLOCKED。 |
| 19 | PARTIAL | 19-api-failure-tests / exit 0；19-final-tests / exit 0；19-independent-venv-create / exit 0；19-independent-install / exit 0；19-independent-reproduce / exit 0；19-causal-evidence-tests / exit 0；19-independent-full-suite / exit 0；19-final-independent-suite / exit 0；19-reliability-report / exit 0；19-reliability-status / exit 2；19-final-independent-suite / exit 0；19-final-independent-suite / exit 0；19-final-independent-suite / exit 0；19-final-independent-suite / exit 0；19-reliability-report / exit 0 | 70项工程测试在独立安装环境通过，1150来源与代表计算复现；全面效果/安全保证不成立。 |
| 20 | PARTIAL | 20-midterm-checkpoint / exit 0；20-evidence-checkpoint / exit 0；20-evidence-checkpoint / exit 0 | 中期验收状态与证据已归档；整体 V3 最终验收未完成。 |

## 操作与下一步

启动和已实现命令见根目录 README。模型只接既有 ChatECNU；没有加载新本地大型模型。已保留原资料、旧核验和失败结果。

优先继续：人工审核精简清单和规则 → 来源侧独立图文标注及截图划分 → 冻结正式金标准并执行60题。继续检验普通知识问答的语义支持和跨任务稳定性；模型语义检查已发生漏检，不能视作正确率证明。增量/干预/独立环境已执行。




AI使用说明：模型辅助编码、候选抽取与工具调度；没有模型代签人审。上下文与计算验证、来源记录和负结果分别保留。
