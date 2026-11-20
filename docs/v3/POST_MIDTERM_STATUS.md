# 中期后开发状态与验收证据

本文件接续 [统一开发文档](DEVELOPMENT_V3.md)、[原中期交付记录](DELIVERY.md) 和 [P00—P12 开发计划](POST_MIDTERM_DEVELOPMENT_PLAN.md)。旧结果、原 60 题、失败运行均保留。以下状态依据已保存的命令、退出码和原始产物，不把测试通过、模型同意或候选激活视为人工审核。

**当前结论：核心工程链路已扩展并运行；完整产品效果尚未验收，产品价值也尚未通过独立样例建立。** 已有真实 Semantica 图谱、来源增量管理、动态 Agent、证据计算、图片候选与工作台。已修复输入与目标授权、显式单位补查、候选交付和预算耗尽结果收束等通用问题；新实体计算走通。多轮真实样例仍暴露知识解释波动、目标过度拆解和未知参数澄清问题，不能把本轮称为全部核心工作完成。

本次状态截点：2026-11-18。旧版全部失败及中断批次保留；最终v4b已在独立 `.venv-repro` 环境通过 **270项完整工程测试**，见 [回归记录](../../artifacts/v3/execution/20261117T162928.359064Z-P12-v4b-full-independent-suite/record.json) 与 [代码冻结](../../artifacts/v3/post_midterm/v4b_code_freeze.json)。真实运行和对照按下方独立版本记录，不能把工程数目当成业务分数。`PASS`仅表示该行所述工程检查；`PARTIAL`表示已实现但存在效果、覆盖或审核欠账；`BLOCKED`表示正式路径的必要条件尚未满足。

## 1. 当前图谱与实现边界

当前候选快照：`7269cd40e0c27ac8a0024bd0db5f10f75687b6a6bd1d6726b49f6c79b7a9b269`。

| 项目 | 已核实状态 |
|---|---|
| 来源 | 26 页可替换的独立来源贡献；31 个与实际来源绑定的旧规则／关系组件 |
| 语义图 | 177 实体、212 事实、250 关系 |
| 图文与来源 | 790 证据、95 图像资产、113 区域、97 观测、817 对齐、4,732 页面出现位置 |
| Semantica | 实际使用 0.7.0 构图与来源存储；独立进程回读检查 1,279 条关键记录及来源 |
| 状态 | 已激活为候选；人工知识审批 0，正式发布 0；游戏版本未核实，来源修订已冻结 |

数据来自 [快照 manifest](../../data/snapshots/7269cd40e0c27ac8a0024bd0db5f10f75687b6a6bd1d6726b49f6c79b7a9b269/manifest.json)、[独立回读](../../artifacts/v3/post_midterm/integrated_roundtrip.json)、[候选激活记录](../../artifacts/v3/post_midterm/candidate_activation.json) 和 [发布审计](../../artifacts/v3/post_midterm/release_audit_integrated.json)。[图谱交接说明](../../artifacts/v3/post_midterm/INTEGRATED_GRAPH_HANDOFF.md) 中“未切换主指针”描述的是当时构建截点；随后只切换候选指针，正式状态未改变。

融合链路为：原文／表格形成文本子图，真实像素形成区域观测；观测与实体、阶段及适用关系对齐；校验方向、条件、依赖和来源后，通过 Semantica 保存多模态对象与来源；审核形成版本化发布边界。检索从同一快照返回实体、关系、任务子图及完整引用，计算器只读显式证据包，动态 Agent 决定检索、补查、计算、澄清与回答。

这不是给图节点附一个图片 URL：区域、像素哈希、观测、对齐、来源和确认等级分别保存。也不是原版 mKG-RAG 全系统复现：原组件运行、接口适配和领域重实现继续按 [METHOD_DIFF.md](METHOD_DIFF.md) 分开记录；原版 QM／EGTR 没有成为默认前置条件。817 条对齐包含结构锚定和阶段示意，不能称为 817 条经人工确认的视觉语义。

新增 Radish／Radish Seeds 两页经通用流程进入图谱，没有加入物品专用调度分支。4 个选择的视觉资产中，2 个返回有效对象，另有 1 次超时、1 次无有效对象；4 条新 ROI 对齐仍待人审。旧来源恢复检查未丢失原非派生记录 ID；撤销 Melon 页会撤销其来源及依赖组件，共享知识由仍有效的其他来源保留。撤销实验是未激活诊断，不能伪称 Wiki 发生了真实修订。

## 2. P00—P12 执行状态

命令索引见下一节，均指向含完整 argv、退出状态和日志路径的实际记录。

| 步骤 | 当前状态 | 实际完成与证据 | 尚未满足的边界 |
|---|---|---|---|
| P00 基线与账本 | PASS | 基线哈希归档；原 70 项在复现环境重跑通过，E01 | 旧产物保留，不把中期建议当作已执行事实 |
| P01 统一契约 | PASS（工程） | 快照、任务修订、依赖、候选／正式、评测可见性契约已接入；E05、E07、E08 | 运行时模型提出的目标不是独立验收金标准 |
| P02 规范化与迁移 | PARTIAL | 受控映射、类型／谓词校验、来源并集及迁移回放；E03；[规范化报告](../../artifacts/v3/post_midterm/normalization-v2.json) | 未知类型、谓词、别名歧义保留待处理；不自动强行合并 |
| P03 图文 ROI 对齐 | PARTIAL | 真实像素、区域约束、跨资产拒绝、结构／语义确认等级；新页线上抽取 E02 | 超时和无对象保留；语义正确性没有独立人审分数 |
| P04 来源与增量 | PASS（已测工程范围） | 旧逐页来源恢复、新两页导入、无变更幂等、撤销新页恢复旧图哈希、撤销旧页使依赖失效；E03、E04 | 真实后续 Wiki 修订仍需重新采集和抽取；旧组件不能脱离旧来源复用 |
| P05 审核闭包与能力 | PARTIAL／正式阻断 | 依赖闭包与发布引用边界回归；18 项图文审核包已导出；E06、E08、E10 | 真实知识／规则审批 0，不能发布正式图；系统依赖闭包不能代替人的语义判断 |
| P06 任务与权限 | PARTIAL | 用户输入、计划库存、ROI、任务修订与取消生效；模型不能冒充确认；E05、E08、E17 | v2 已恢复“果酱”“春27日”，并堵住模型目标、截短原文及伪库存授权路径；自然语言提取仍需独立语义评测 |
| P07 混合答案与 Agent | PARTIAL | 真实模型工具循环、330／175／1320→880／959 等候选计算及多轮轨迹；v4b预算末尾实际交付有效部分计算；E22 | PM01／04知识段仍未完整；OPEN仅交付Wine方案、缺Jelly与解释，不能报全面完成 |
| P08 视觉候选与拒识 | PARTIAL | 真实上传／框选／候选外纠正；35 个旧开发裁剪全部运行；E11、E17 | 0 个独立新截图；全 35 项要求确认；未证明独立识别优势或可靠自动接受阈值 |
| P09 公平对照与成本 | PARTIAL | 原文产品 baseline、B/BQ/C/D 结构消融、实际 6,000 字符证据预算、代码／模型／预算哈希与逐层成本；E07、E12 | 预声明比较已执行；PM01／11 无图，产品 baseline 有导航噪声；正式胜负未评分，不能证明图结构或视觉优势 |
| P10 统一工作台 | PARTIAL | 浏览器完成上传、框选、候选外纠正、525g 候选计算、改量后旧结果失效、取消及来源查看；E17；最终v4b重新启动并核对同快照图文审阅 | 是工程交互演练，非独立用户研究；最终后端的完整图文任务链仍需综合验收 |
| P11 评测工具与数据 | PARTIAL／正式阻断 | validate、export-review、freeze、run、score、compare；保留全部 turns；旧 60 题完整导出；12 题全量诊断；E09、E13—E16 | 旧题为实现后开发集；独立金标准／结果人审 0，正式冻结被正确阻断；旧 9 个缺图交互未全部补齐 |
| P12 综合交付 | PARTIAL | v1 213、v2 250、v3 261、最终v4b 270工程测试通过；各版真实模型、新进程重载及算术复现分别记录 | 正式产品验收、知识解释可靠性和独立效果仍未完成，不能以工程通过代替 |

## 3. 实际命令、退出状态与产物

下表缩写 `PY` 为 `.venv-repro/bin/python`；完整参数以每行记录文件为准。退出码 2 在审核导出、冻结门槛和候选评分中表示待审／不满足正式条件，不自动代表程序崩溃。测试失败、模型失败与部分答案均保留，不能因外层 CLI 退出 0 就记为问题解答成功。

| 索引 | 实际命令／检查 | 退出与结果 | 原始记录与产物 |
|---|---|---|---|
| E01 | `PY -m pytest -q tests`（原基线） | 0；70 PASS | [record](../../artifacts/v3/execution/20261117T091441.410679Z-P00-resume-baseline-loopback/record.json)、[baseline](../../artifacts/v3/post_midterm/baseline.json) |
| E02 | 新 Radish 双页在线图文建图 | 0；两个视觉失败单列保存 | [record](../../artifacts/v3/execution/20261117T115937.251823Z-P03-P04-new-page-online-v2/record.json)、[逐页产物](../../data/post_midterm/radish_diagnostic_v2/pages/) |
| E03 | `PY scripts/post_midterm_integrate.py`；图谱相关 pytest | 0；集成候选；58 PASS | [集成命令](../../artifacts/v3/execution/20261117T123314.589368Z-P04-integrated-replayable-final/record.json)、[58 项记录](../../artifacts/v3/execution/20261117T123525.442029Z-P02-P05-integrated-graph-regression/record.json)、[来源恢复](../../artifacts/v3/post_midterm/source_recovery/result.json) |
| E04 | 同注册表重放、撤销新／旧页与图哈希断言 | 0；PASS | [record](../../artifacts/v3/execution/20261117T123524.291612Z-P04-integrated-incremental-replay-checks/record.json)、[检查结果](../../artifacts/v3/post_midterm/incremental_replay_checks.json) |
| E05 | task contract／completion／grounding／runtime 回归 | 0 | [契约记录](../../artifacts/v3/execution/20261117T115312.649952Z-P06-P07-agent-contract-verified/record.json)、[权限边界记录](../../artifacts/v3/execution/20261117T122602.002963Z-P07-authority-formal-boundary/record.json) |
| E06 | `PY scripts/post_midterm_review_packet.py --snapshot … --output …` | 2；18 项 PENDING_HUMAN | [record](../../artifacts/v3/execution/20261117T124555.088619Z-P05-final-review-packet/record.json)、[图文审核页](../../artifacts/v3/post_midterm/review-integrated/index.html) |
| E07 | visible budget／evaluation／product／reranking／runtime／evidence 回归 | 0；79 PASS | [record](../../artifacts/v3/execution/20261117T123553.750231Z-P11-visible-evidence-budget-tests/record.json) |
| E08 | `PY -m pytest -q tests`（v1 集成代码） | 0；213 PASS | [record](../../artifacts/v3/execution/20261117T123847.110657Z-P12-integrated-full-suite/record.json)、[完整 stdout](../../artifacts/v3/execution/20261117T123847.110657Z-P12-integrated-full-suite/stdout.log) |
| E09 | `post_midterm_evaluation.py prepare-legacy`；visual v2 validate／freeze | 2 待审；validate 0；freeze 2 正确拦截 | [完整多轮导出](../../artifacts/v3/execution/20261117T115125.897275Z-P11-legacy60-full-turns/record.json)、[验证](../../artifacts/v3/execution/20261117T121702.574563Z-P11-visual-v2-validate/record.json)、[冻结门槛](../../artifacts/v3/execution/20261117T121702.574570Z-P11-visual-v2-human-gate/record.json) |
| E10 | `PY -m stardew_agent release-audit --snapshot-id … --output …` | 2；NO_HUMAN_APPROVALS | [record](../../artifacts/v3/execution/20261117T124634.352600Z-P05-final-release-audit/record.json)、[结果](../../artifacts/v3/post_midterm/release_audit_integrated.json) |
| E11 | `PY scripts/post_midterm_visual_diagnostic.py --snapshot … --output …` | 0；35/35 执行，人工真值待审 | [record](../../artifacts/v3/execution/20261117T124555.088622Z-P11-final-visual35/record.json)、[完整分母诊断](../../artifacts/v3/post_midterm/visual_diagnostic/integrated-reused35/summary.json) |
| E12 | c704 真实证据包预算审计（无模型调用） | 0；B/BQ/C/D 实长均 ≤6,000 | [record](../../artifacts/v3/execution/20261117T123817.528769Z-P11-c704-visible-budget-audit/record.json)、[实际长度](../../artifacts/v3/post_midterm/evaluation/visible-budget-c704-audit.json) |
| E13 | `post_midterm_evaluation.py run --method D --online --mode exploratory`，全 12 题 | 0；EXECUTED，不代表 12 题成功 | [record](../../artifacts/v3/execution/20261117T124604.052077Z-P11-final-live-D-all12/record.json)、[完整 v1 run](../../artifacts/v3/post_midterm/evaluation/final-D-all12/run.json) |
| E14 | `post_midterm_evaluation.py score --run …/final-D-all12/run.json` | 2；4 FAIL、8 PENDING_HUMAN | [record](../../artifacts/v3/execution/20261117T125220.563583Z-P11-final-v1-all12-score/record.json)、[v1 分数文件](../../artifacts/v3/post_midterm/evaluation/final-D-all12-score.json) |
| E15 | retry v2：原 12 题全部重跑及评分 | run 0；score 2，12 PENDING_HUMAN | [250 项完整回归](../../artifacts/v3/execution/20261117T132054.653629Z-P06-P07-agent-v2-final-repro-all/record.json)、[执行记录](../../artifacts/v3/execution/20261117T132129.798777Z-P11-v2-all12-driver/record.json)、[结果](../../artifacts/v3/post_midterm/evaluation/final-v2-D-all12-score.json) |
| E16 | B/BQ/C/D：PM01、PM11；product/D：PM03、PM04 | 执行器 0；各 run 0、score 2；compare 0／UNSCORED | [执行记录](../../artifacts/v3/execution/20261117T132854.704774Z-P11-v2-declared-comparisons-driver/record.json)、[结构对照](../../artifacts/v3/post_midterm/evaluation/final-v2-structure-comparison.json)、[产品对照](../../artifacts/v3/post_midterm/evaluation/final-v2-product-comparison.json) |
| E17 | `PY -m pytest -q tests/test_workbench_lifecycle.py`；真实浏览器演练 | 0；2 PASS；交互检查已记录 | [record](../../artifacts/v3/execution/20261117T115847.886674Z-P10-workbench-lifecycle/record.json)、[浏览器事件与检查](../../artifacts/v3/post_midterm/ui/run.json)、[取消／纠正截图](../../artifacts/v3/post_midterm/ui/correction-cancellation.jpg)、[集成来源页](../../artifacts/v3/post_midterm/ui/integrated-source-review.jpg) |
| E18 | `PY scripts/post_midterm_reproduce.py --snapshot … --output …` | 0；新进程、离线；330／525 显式算术通过 | [record](../../artifacts/v3/execution/20261117T124153.955239Z-P12-fresh-process-reproduce/record.json)、[结果](../../artifacts/v3/post_midterm/reproduce-integrated.json) |
| E19 | v3 完整工程回归、全12题及 NEW/OPEN 顺序重跑 | 测试0／261 PASS；三个run 0，score均2；OPEN仍FAIL | [261项](../../artifacts/v3/execution/20261117T135018.822418Z-P06-P07-agent-v3-final-format-guard-all/record.json)、[12题](../../artifacts/v3/execution/20261117T135210.763410Z-P11-v3-all12-driver/record.json)、[NEW](../../artifacts/v3/execution/20261117T161607.661522Z-P11-v3-new-entity-driver/record.json)、[OPEN](../../artifacts/v3/execution/20261117T161702.095868Z-P11-v3-open-comparison-driver/record.json) |
| E20 | v4预算收束后审查、v4b视觉候选交付修复与全套回归 | v4测试268 PASS；在线批次主动中断130；v4b测试0／270 PASS | [中断原因与原日志](../../artifacts/v3/post_midterm/v4_interruption_record.json)、[v4b专项103项](../../artifacts/v3/execution/20261117T162840.803575Z-P06-P07-agent-v4b-visual-finalization-focused/record.json)、[最终270项](../../artifacts/v3/execution/20261117T162928.359064Z-P12-v4b-full-independent-suite/record.json) |
| E21 | 重启v4b本机服务，读取bootstrap并浏览真实来源/区域 | 0；候选7269，正式null，未执行审批 | [record](../../artifacts/v3/execution/20261117T163248.183216Z-P10-final-v4b-workbench-check/record.json)、[脱敏接口记录](../../artifacts/v3/post_midterm/ui/final_v4b_bootstrap.json)、[最终截图](../../artifacts/v3/post_midterm/ui/final-v4b-source-review.jpg) |
| E22 | 冻结v4b：原12题全部重跑，随后NEW与OPEN，不改题目或预算 | 三个run均0；score均2；12题+NEW待审，OPEN整体FAIL | [12题执行](../../artifacts/v3/execution/20261117T163011.875516Z-P11-v4b-all12-driver/record.json)、[NEW执行](../../artifacts/v3/execution/20261117T163412.996464Z-P11-v4b-new-entity-driver/record.json)、[OPEN执行](../../artifacts/v3/execution/20261117T163452.126521Z-P11-v4b-open-comparison-driver/record.json)、[全12题评分](../../artifacts/v3/post_midterm/evaluation/final-v4b-D-all12-score.json)、[OPEN评分](../../artifacts/v3/post_midterm/evaluation/final-v4b-open-comparison-score.json) |
| E23 | 最终产物完整性核对（不调用模型） | 0；7项保护文件未变，186个文档链接有效，三组运行代码/模型/预算一致；仅完整性PASS | [record](../../artifacts/v3/execution/20261117T163923.937136Z-P12-final-delivery-integrity/record.json)、[完整性报告](../../artifacts/v3/post_midterm/final_delivery_integrity.json) |

完整命令历史及早期失败见 [execution.jsonl](../../artifacts/v3/execution.jsonl)。曾有一次完整测试因沙箱拒绝 loopback 端口而失败；随后单项复核及 E08 全套允许本机端口的复跑均通过。它与真实问答失败分别记录。

## 4. 修复前 v1 的实际表现

这 12 题属于**实现后开发诊断**，已在开发期间查看和调试；不是新盲测。全部 turns、工具调用、状态、引用及失败已保存。[详细逐题解释](POST_MIDTERM_EVALUATION_NOTES.md) 是解读依据，不能把 `PENDING_HUMAN` 折算成成功。

| 案例 | v1 观察到的结果 | 解释边界 |
|---|---|---|
| PM01 季节与生长知识 | 最终校验失败 | 证据已检出，但阶段序号／来源修订数字及候选知识语义检查阻断答案 |
| PM02 简单售价 | 输出 330g | 候选算术成立，独立内容审核仍待完成 |
| PM03 先预留再出售 | 预留后剩 5 个，出售 175g | 原库存不变；期间一次计划冲突后恢复，不能称首次无错 |
| PM04 计算＋知识解释 | 只交付 330g，标注部分完成 | 季节／生长解释未交付，混合目标不成功 |
| PM05 多轮改数量 | 1,320g → 880g | 12→8 的修订与计算引用更新可查 |
| PM06 果酒改果酱 | 首轮 1,500g；第二轮未给 1,100g | 合法中文“果酱”被输入 guard 拒绝，要求英文是实现缺陷 |
| PM07 缺参数 | 请求数量、品质、职业 | 没有偷偷按 1 个计算；澄清内容仍需人审 |
| PM08 模组＋全局最优 | 请求额外资料，没有伪造收益 | 未充分说明全局排程能力边界，不能宣称已处理该目标 |
| PM09 看图识物 | 已检出 Parsnip 候选，最终答案校验失败 | 有候选不等于用户收到可用识别结果 |
| PM10 阶段图 | 请求确认作物、阶段与已生长情况 | 保留歧义；旧草稿标签未人审，不能据此评分准确率 |
| PM11 550g＋春27日生长 | 算过 550g，但最终只要求季节确认 | “春27日”被过严校验；两项目标均未在最终答案完成 |
| PM12 澄清后续答 | 第二轮给 959g | 首轮文字曾提出默认值，虽实际 guard 拒绝，仍是需要修复的表达缺陷 |

v1 运行内代码和公开模型配置未变化；模型为 ChatECNU `ecnu-max` 文本、`ecnu-plus` 视觉。18 次检索／补查证据块最大 5,990 Unicode 字符，未发现该预算违例；全部工具消息累计字符代理为 192,087。6,000 限制的是每次初检或显式补查的模型可见证据块，**不是整个对话上下文**；来源段落、事实、关系、实体和图像引用计入。所有工具消息（含规则发现、计算和证据查询）的字符累计另记，不能冒充 token、费用或完整模型上下文长度。

35 图诊断全部来自已用开发截图族，原助理草稿标签未经独立人审。完整 19 个旧已知标签中 Top1 命中 11、Top3 命中 12；其中 6 个标签不在当前图库，必须留在总体分母内。全部 35 项都返回需确认，自动确认 0。该结果仅描述“复用开发标签的候选一致情况”，不是自动识别准确率，也未证明图像带来产品优势。


## 4.1 v2 全量与对照的增量结果

v2 的 12 题含 15 轮、18 个独立草标目标：**11 个计算目标的当前引用凭据与显式期望相符，2 个终态检查通过，5 个知识/视觉目标仍需内容核对**。全部 12 题评分状态为 `PENDING_HUMAN`。PM01 在全量批中只交付春季，不能将“无自动 FAIL”解释为全题成功。完整原问题、最终文本及图像见 [v2 实际回答待审清单](../../artifacts/v3/post_midterm/evaluation/v2_实际回答待审.md)。

结构子集只含两个无图开发问题。B/BQ/C/D 在 PM11 均给出 550g 和季末无法成熟；PM01 的完整程度不同，同代码 D 在不同批次也出现完整／部分回答的变化。没有独立审核的必要证据组，初检充分率为 null。两组比较均 `formal=false`、`UNSCORED`，不报告方法排名。

产品 baseline 直接检索原始页面，但重复导航表与无关 Blueberry 图挤占了预算，两题没有给出所需完整数值；该原型基线需要改进，不能作为“图谱优于成熟 RAG”的证据。D 在产品对照 PM03 交付预留与175g，PM04 仍只交付330g。较好的其他批次不替换这次失败。

额外诊断分开保留：NEW-01 新 Radish 得到 **4×90=360g**，见 [新实体结果](../../artifacts/v3/post_midterm/evaluation/final-v2-new-entity/run.json)；OPEN-01 未点名产物的加工比较 **BUDGET_STOP**，见 [开放比较结果](../../artifacts/v3/post_midterm/evaluation/final-v2-open-comparison/run.json)。后者其实已经找到 Wine 与 Jelly，失败来自比较目标契约、旧 bundle 和递进补查的调度开销，而非缺少这两个产物。

v3 仅修通用工具契约可发现性、错误反馈和有界输出格式可靠性，保持题目、原期望、12轮与证据预算不变，见 [重跑声明](../../artifacts/v3/post_midterm/v3_retry_declaration.json)。v2 对照属于 v2 代码，不与 v3 混成同版本成绩。

## 4.2 v3 全量及额外诊断

v3 冻结代码 `2eddb1d07cca88a58a2c63feee877304da5dc7bc23404c51ca6187856d5e8ddc`，261 项工程测试通过。全12题仍为12个 `PENDING_HUMAN`，11个计算子目标和2个终态检查符合草标，5个知识/视觉目标待审。90条工具消息累计210,628字符；22次证据块最大5,986字符，无该预算违例。运行过程中代码及模型配置未变。

PM01 这次完整交付中文春季、6个有效夜晚及浇水条件；PM04也交付330g及这些知识，但模型多登记了未请求的动态生长计算目标，最终假性 `PARTIAL`。PM10仍重复索要用户明确不知道的阶段内已过夜晚，未充分利用区间能力。格式重检本批实际触发0次，只能称该分支已有工程回归，不能声称真实线上验证了它。

NEW-01再次得到360g。OPEN-01在12轮内已得到Wine1500g、Jelly1100g、原料500g的当前回执，comparison覆盖满足，但另一知识目标未交付；最终只给循环上限提示，仍为 `BUDGET_STOP / FAIL`。不能把后台receipt当成用户已经收到的完整方案。全部14题17轮原文、实际回答、图片与引用见 [v3待审清单](../../artifacts/v3/post_midterm/evaluation/v3_实际回答待审.md)。这项失败要求继续实现通用的预算耗尽结果收束，保留已有计算并明确未完成知识目标，而不是增加轮次或修改期望。

## 4.3 最终v4b诊断与尚未解决的问题

冻结代码 `6f3d012b32f36cf09910be490c31873d54b09c4860ce8e608acaf0880779ac98`，270项工程回归通过。v4曾通过268项但交叉审查发现预算收束遗漏视觉候选展示；该批主动中断，已落盘PM01失败和PM02算术保留，退出130，不能算完整批次。v4b新增混合候选/身份确认回归后重新完整运行，未修改问题、参考目标、图片、快照或12轮上限。

最终12题的11个计算子目标与2个终态检查符合草标，5个知识/视觉目标待审；评分12个`PENDING_HUMAN`。PM01仅交付春季，PM04仅交付330g，仍未完成知识解释。PM05/06经工具错误后恢复；PM12第一轮模型尝试写入未提供默认值，被参数guard拒绝后才正确澄清。不能把guard挡住错误尝试等同于模型从不尝试错误输入。

这批88条工具消息累计186,418字符；17次证据块最大5,986字符，代码、模型及预算核对通过。最多9轮，预算收束与格式重检均未触发；不能从本批宣称这些分支已在线验证。

NEW-01用7轮交付360g。OPEN-01真实触发了新的预算收束：12轮后向用户交付Wine1,500g、直接出售原料500g、差额1,000g，并明确“解释依据、完整方案比较”未完成；额外模型调用0。该批未完成Jelly1,100g，评分仍为**FAIL**。v3算到两个后台结果与v4b交付一个结果属于不同运行，不能拼成一次成功。实际新结论仅为“预算耗尽可保留并显示有效部分结果”，开放任务完整交付仍待改进。

全部真实原文、实际答案、引用、ROI、恢复错误和待审标签保留在[最终实际回答清单](../../artifacts/v3/post_midterm/evaluation/v4b_实际回答待审.md)及[逐题解读](POST_MIDTERM_EVALUATION_NOTES.md)。当前正式成功率仍为null，未用重试挑选最好回答。

## 5. A01—A30 更新验收矩阵

沿用原文中的验收名称与范围；新状态不会抹掉旧证据。标为工程 PASS 的项目仍受候选知识和正式审核边界约束。

| ID | 原验收项 | 当前状态 | 可核查证据与剩余限制 |
|---|---|---|---|
| A01 | 保留真实基线 | PASS | E01、[旧基线完整性](../../artifacts/v3/baseline_integrity_final.json)；v1 失败原样保留 |
| A02 | 复用边界明确 | PASS | [METHOD_DIFF](METHOD_DIFF.md)、[原组件运行](../../artifacts/v3/upstream/component_run.json)；未声称全系统 QM／EGTR 复现 |
| A03 | 图文关联分段 | PARTIAL | E02—E04；页面出现位置、原图和区域保留；语义分段质量待独立审核 |
| A04 | 通用文本建图 | PASS（工程） | E02、E03；新 Radish 同模板两页无需专用业务分支；不代表任意页面都正确 |
| A05 | 实际视觉抽取 | PASS（执行） | E02；请求含真实像素，有对象／区域与真实超时、无对象记录 |
| A06 | 实体级对齐 | PARTIAL | E02、E11；跨资产／错区域负例和候选保留；实体正确率未独立评定 |
| A07 | 阶段级对齐 | PARTIAL | E03；CropStage、阶段持续事实及共享像素分开；PM10 仍有歧义、待审 |
| A08 | 关系级对齐能力 | PARTIAL | [复合图原始结果](../../artifacts/v3/evaluation/compound_summary.json)、新图来源链；关系方向／目标语义效果待审 |
| A09 | 可区分原始图像与页面渲染 | PASS | E02；原 URL PNG、浏览器 DOM、派生裁剪来源分别标注 |
| A10 | Semantica 多模态融合 | PASS（工程） | [集成回读](../../artifacts/v3/post_midterm/integrated_roundtrip.json)；1,279 关键来源记录独立进程复核 |
| A11 | 有向多谓词语义 | PASS（工程） | E03、E08；规范化与回放保持方向、谓词、条件及来源 |
| A12 | 审核与版本 | PARTIAL | E06、E10；正式门槛与快照绑定可用；0 人审，0 正式发布 |
| A13 | 批量与增量 | PASS（已测范围） | E03、E04；新增、幂等、来源撤销、依赖失效和旧图恢复 |
| A14 | 图片缓存隔离 | PASS（工程） | E07、E08；图像字节、ROI、任务绑定与规则实现指纹篡改拒绝 |
| A15 | 建图效果可解释 | PARTIAL | [旧 K0/K1 诊断](../../artifacts/v3/evaluation/construction_summary.json)；独立效果评分尚无，不能报提升 |
| A16 | 真多粒度检索 | PASS（工程） | E07、E12、E13；实体、关系和任务子图真实 ID；selected IDs 与实际可见证据一致 |
| A17 | 问题感知 | PARTIAL | [旧换图干预](../../artifacts/v3/evaluation/isolated_image_retrieval_summary.json)；新预声明结构题无图，尚不能证明视觉重排优势 |
| A18 | 无隐藏补查 | PASS（已测工程范围） | E07、E08；计算器无图查询权限，依赖补查有独立工具与预算；v2 已包括单位补查、实际可见闭包与预算回归 |
| A19 | 证据与结果因果联系 | PASS（工程） | E08；相关／无关事实、关键边、唯一／冗余来源及实现指纹干预测试 |
| A20 | 参数与知识分离 | PASS（工程） | E05、E08、PM03；用户值、知识值、计算 receipt、原库存和计划副本分别保存 |
| A21 | 真实 Agent | PARTIAL | 新Radish360g无专用分支接入；v4b OPEN交付Wine有效部分但缺Jelly与解释，整题仍FAIL；不能以不同批次结果拼成成功 |
| A22 | 澄清与纠正 | PARTIAL | v2 PM05、06、11、12 实际恢复；旧值失效与别名／日期接线已有回归，仍记录恢复过程的工具错误 |
| A23 | 计划库存正确 | PASS（已测范围） | PM03 预留后剩 5 个／175g，原库存未改；计划冲突可拒绝并恢复 |
| A24 | 图片确认可控 | PARTIAL | E11、E17；模型无权伪造确认、可候选外纠正；自动接受阈值未独立校准 |
| A25 | 建库过程可视 | PASS（工程） | E06、E17；图文审核页、引用、区域和当前绑定快照可查看 |
| A26 | 通用工作台 | PARTIAL | E17真浏览器链路可运行，E21确认最终后端的图文来源审阅；最终全链路、全目标及导出仍需综合验收 |
| A27 | 公平检索对照 | PARTIAL | E16 同版本预算与元数据过检；小样本、独立证据组缺失、baseline 导航噪声使效果结论仍未成立 |
| A28 | 正式评价不泄漏 | BLOCKED | E09；保留完整多轮、源图族及标签来源；独立新集、真实金标审批与冻结未完成 |
| A29 | 错误与安全 | PARTIAL | 最终270项含身份／原文截断／伪库存／可见闭包／取消与预算收束反例；澄清无默认，知识拒答和模型格式仍有可靠性缺口 |
| A30 | 复现可检查 | PASS（已测工程范围） | E18；复现环境新进程离线重载、来源核查和显式算术；真实线上效果不能由离线 smoke 替代 |

## 6. 后续执行队列与完成条件

以下沿用 P00—P12，不新增时间排期。每轮变更须保存失败旧版、重新冻结代码并跑完整相关样例；不能只替换较好的回答。

| 顺序 | 工作 | 实现约束与完成条件 | 产物 |
|---|---|---|---|
| R00 | 新页面建图语义验收与真实修订 | 冻结未参与开发的新页面、像素与独立实体/状态/关系/条件标注；比较文本、结构锚点及像素融合，分开自动与纠正后结果；完成两个不重叠增量批次及真实来源修订影响Agent答案的链路，不把模拟撤销充当真实修订 | 新页分组、三种构图输出、语义差异、误对齐与修订前后来源/派生记录/答案证据；与R01并行 |
| R01 | 开放任务调度和目标契约 | 预算耗尽有效结果交付已补好，继续减少分散依赖补查及错误目标拆解；保持12轮与同证据预算，未知elapsed进入可支持区间而非反复索要；从真实关系发现备选并完整交付，不按题号/物品专用路由 | v4b原始失败及回归基线、依赖发现接口、目标必要性诊断；需新变体检验完整比较，不能仅把PARTIAL改名成功 |
| R02 | 知识解释与检查可靠性 | 区分候选模式的语义支持与正式审核许可；不得因未审自动判所有候选语义无效，也不得跳过真实支持检查。阶段编号/数量/耗时分型，抑制未请求且无依据的细节，确保中文知识段与计算都交付 | PM01/04及候选-正式/阶段-天数正反例、有界格式日志、新变体与稳定性诊断；保留此前全部模型失败 |
| R03 | 改善朴素产品 baseline | 通用去除重复导航、目录与页脚；按原始正文/表格和公开名称关联召回；不得读取图事实、预期答案或给某题补特供上下文；参考图只能来自实际选中正文附近 | 原文chunk清单、检索相关性审阅包、新版同条件product/D对照；旧弱baseline结果保留 |
| R04 | 检索预算下的证据充分性 | 简单属性查询与关系/任务子图区分；避免无关NEXT_STAGE挤占目标事实。独立标注必要证据与等价来源，模块对照固定query/入口ID/条件/ROI重放B/BQ/C/D，Agent改写另测；正式协议冻结分层分母、门槛、重复次数与不确定性，不让gold进入Agent | 分组与证据集草标、人审文件、冻结协议、逐题初检/补查/完整任务结果；内部门槛见计划6.4 |
| R05 | 独立视觉区间检验 | 按原截图族收集新素材，分别测已知图库物品、新扩库实体和确实库外对象；开发集校准后冻结，报告全部分母、错误接受和确认负担；复用35裁剪仍只用于回归 | 原图/ROI哈希、分组、草标与人审包；独立视觉结果和同图异问/换图干预 |
| R06 | 按明确能力发布知识 | 从实际要支持的能力反推事实、关系、规则和视觉依赖；输出精简图文审核包。真实人工审核后检查完整闭包、实现指纹及冲突，再发布；未知谓词不自动变成已批准知识 | 审核记录、能力报告、正式快照、旧任务回放与增量撤销验证 |
| R07 | 产品工作台与正式验收 | 在最终后端上完整走上传、确认、混合问题、比较、纠正、取消、历史与导出；使用冻结独立题集及被核验来源，不将工程演练称为真实用户研究 | 最终UI图文证据、正式评价记录、A01—A30更新、复现包 |

R00—R04 的工程工作可以自主进行；R05 的采集和草标也可先做。真正的人审、独立金标准批准与正式发布依赖不能由模型代签。当前视觉的“已在图库内”子组只用于提出下一轮假设，不通过事后删掉图库缺项来宣称已经存在识别优势。

## 7. 必须由真实人工完成的审核

人工审核不阻塞以上独立工程工作，但以下门槛不能由开发脚本或另一个模型代签：

| 审核类别 | 材料 | 审核对象与批准边界 |
|---|---|---|
| 知识／视觉／规则发布审核 | [18 项精简图文清单](../../artifacts/v3/post_midterm/review-integrated/待审证据清单.md)、[图文页](../../artifacts/v3/post_midterm/review-integrated/index.html) | 对照原文／原像素确认实体、阶段、方向、条件与公式；审核包是优先子集，不代表整库已审。系统再验证依赖闭包、哈希与发布完整性 |
| 独立金标准审核 | [完整 12 题逐轮目录](../../evaluation/datasets/post_midterm/visual_ready_v2/review/完整逐轮待审目录.md)、[旧 60 题完整目录](../../evaluation/datasets/post_midterm/legacy60/review/完整逐轮待审目录.md) | 逐轮独立期望、缺参边界、允许部分答案与视觉真值；旧实现生成的参考答案不可直接当正式 gold |
| 产品输出审核 | [最终v4b清单](../../artifacts/v3/post_midterm/evaluation/v4b_实际回答待审.md)；旧v1/v2/v3及中断v4仍保留 | 判断全目标是否真正完成、引用是否支持、澄清是否合理、图片是否减少用户负担；评审记录须绑定 case/run hash |

知识审批、金标准审批、结果内容评审是三类记录。完成其中一类不自动批准另外两类。当前正式成功率为 `null`，不是 0% 也不是已通过；正式发布数和真实审批数为 0。正式整体验收与“相比普通 RAG 更有用”的结论仍待独立证据。
