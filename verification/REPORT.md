# 技术可行性核验实测报告

日期：2026-11-12。**工程结论：Conditional Go，支持继续开发限定范围的原型；不能认定完整项目计划已全部通过。方法结论：图谱相对平面图文检索的收益尚不明显。** 本轮已交付可运行代码、真实来源、模型接口和离线复跑；不是只有方案文字，也不是完整成品网页。

## 执行汇总

下表的 PARTIAL 保留原计划门槛，不能折算为完整 PASS。程序内的 `PASS_DIAGNOSTIC` 仅代表对应小样断言成立。

| 核验 | 验收状态 | 实际命令（`.venv/bin/python -m` 后缀） | 实测结果与证据 | 限制和下一步 |
|---|---|---|---|---|
| V00 环境 | PASS | 原环境 smoke 脚本 | Python 3.12.14 / arm64；Semantica 0.7.0；此前 87 项环境断言通过；`ENVIRONMENT.md` | 系统 Python 未改；不是业务验证成绩 |
| V01 真实语料 | PARTIAL | `verification.knowledge` | 12 页、37 个图片资源、2239 个图片出现位置，其中 872 个与当前图库对齐；71 条事实；`results/v01.json` | 精确游戏版本、独立审核与逐素材再分发许可待确认；HTTP 抓取受限 |
| V02 Semantica | PASS | `verification.graph` | 1001 节点、1937 边；来源 SQLite；独立进程重载；16 项断言通过；`results/v02.json` | 专用 Wiki 解析器和查询适配器不属于 Semantica 内建功能 |
| V03 视觉候选 | PARTIAL | `verification.vision` | 9 张网上原图裁出 35 个区域，按来源分组；测试已知 Top-3 为 14/14；`results/visual_metrics.json` | 仅 2 个测试阶段样本；未达到 48 图及独立标签审核要求；见分层结果 |
| V04 检索适配 | PARTIAL | `verification.retrieval` | 4 开发题、16 测试题；同候选/预算比较；B、D 均 10/14 完整证据；`results/v04.json` | 两组配对类型调整；部分前提召回缺失；关系评价和条件一致性尚未独立核准 |
| V05 规则计算 | PARTIAL | `verification.probes.calculation_probe` | 12 类、39 项断言全部通过；相关/无关事实干预、唯一/冗余来源、旧索引均有测试；`results/v05.json` | 冻结 Wiki 诊断；独立手算复核和目标版本尚未完成 |
| V06 ChatECNU | 接口 PASS，效果有限 | `verification.chatecnu` 等 | 两模型文本/JSON/工具调用/图片输入均实际测试；真实工具往返通过；合计 34 次请求 | 细粒度视觉分类有失败；不能把“支持图片”当作识别可靠 |
| V07 端到端 | PARTIAL | `verification.pipeline` | 两正向 + 六异常及恢复，共 8/8 诊断检查通过；`results/v07.json` | 阶段必须确认；未知例含脚本拒绝候选；不是用户实验或全场景成功率 |
| V08 复跑 | PARTIAL，离线机制通过 | `verification.run_all --offline` | 新进程重新执行核心步骤，禁网络；哈希与实际退出码见 `results/v08.json`、`results/runs/` | 完整门槛未满足，退出码 2；在线模型记录只复用，不伪装新调用 |
| 专项连接 | PASS，限工程适配 | `verification.probes.mkgrag_semantica_probe` | 22 项断言；截图、Wiki 图、真实图路径、多粒度证据、同图异问、计算依赖贯通 | 详见 `MKG_SEMANTICA.md`；不是原论文训练模型复现 |

1001 个节点包含 872 个图片出现位置、71 个 Fact、12 个 Source；它不意味着覆盖了 1001 种游戏物品。领域范围目前只有防风草、甜瓜、蓝莓、两类加工设备及相关基础规则。

## 三个关键原始案例

**图谱查询与来源。** `Parsnip_Seeds → GROWS_INTO → Parsnip → HAS_FACT → fact:Parsnip:growth_days → SUPPORTED_BY → source:Parsnip` 是真实导出图中的路径。值为 4，单位为 `growth_nights`，位置为 infobox 的 Growth Time 行，来源为 [Parsnip 修订 191123](https://stardewvalleywiki.com/mediawiki/index.php?title=Parsnip&oldid=191123)。JSON、SQLite 与源文件哈希共同核对，见 `results/mkgrag_semantica.json` 和 `artifacts/graph/`。

**真实截图候选。** V28 来自 [Steam 玩家攻略](https://steamcommunity.com/sharedfiles/filedetails/?id=812004740) 的背包格。模板的首候选是 Parsnip Seeds，并提供 Wiki 图片 ID 和 occurrence；不是从截图文件名读取答案。V10 来自 [Arqade 原帖](https://gaming.stackexchange.com/questions/298179/why-did-these-plants-wither)，作者说明种的是甜瓜，但幼苗像素与其他作物阶段相似。模板保留多个候选；ChatECNU 参考图补测仍将其误认成防风草阶段。逐图结果见 `results/visual_predictions.jsonl`、`results/model_reference_pilot.json`；原始裁剪与联系图保留本地。

**确定性计算。** 春 23 日购买并种植 50 株防风草，每天浇水、无加速、普通品质：春 27 日成熟，成本 1000g，销售额 1750g，仅扣种子成本收益 750g。这些数由 [Parsnip Seeds 修订 193542](https://stardewvalleywiki.com/mediawiki/index.php?title=Parsnip_Seeds&oldid=193542)、作物规则和用户输入得到。隔离快照将出售价格从 35g 改成 40g，收益变为 1000g；修改甜瓜价格不影响该题。删除关键边或唯一有效来源会拒算。完整轨迹见 `artifacts/calculation_trace.json`、`artifacts/interventions/`。

ChatECNU 的真实工具链先生成上述任务参数，再调用本地函数，最后依据工具结果输出中文与原样数值；`results/model_workflow.json` 保存实际响应和校验，不使用手写模型 fixture 充当结果。

## 视觉成绩必须按样本类型理解

原计划要求 48 图：24 个已知物品/种子、12 个已知阶段、12 个未知。本轮实际是 35 个裁剪：16 个物品/种子、3 个阶段、16 个未知；开发 11 个、测试 24 个。9 张源截图分别留在一个 split，未把同一截图的缩放版本分到训练和测试。图片来自公开网页，有不同年代、界面和未知模组状态，不能称为指定原版版本的测评。

| 模板匹配结果 | 开发集 | 测试集 |
|---|---:|---:|
| 已知样本 | 5 | 14 |
| Top-1 命中 | 4/5 | 13/14 |
| Top-3 命中 | 5/5 | 14/14 |
| 其中物品 Top-3 | 4/4 | 12/12 |
| 其中阶段 Top-3 | 1/1 | 2/2 |
| 已知样本自动接受 | 1/5 | 12/14 |
| 未知样本没有自动接受 | 5/6 | 10/10 |
| 所有自动接受中的错误 | 1/2 | 0/12 |

测试中的 12 个已知物品含 6 个收藏菜单图标，不全是背包物品格。两个未知阶段区域的物种标签仍属临时判断，保守排除它们后，未知非自动接受结果为 8/8；完整 10 个结果也保留，没有删除不利成绩。测试延迟中位约 0.27 秒，P95 约 0.45 秒，硬件/输入范围有限。

开发集 V11 的枯萎植物被模板自动误认成已知阶段，说明仅靠分数阈值不可靠。当前流程让所有阶段先确认，再给区间；数量和品质仍由用户输入，未实施 OCR。上述视觉成绩是基础匹配器成绩，不能用它冒充保守确认策略之后的自动覆盖率。

对同一批 12 个代表区域（8 已知、4 未知），`ecnu-plus` 的直接图像分类已知 Top-1 为 2/8，未知非自动接受为 3/4。加入三个 Wiki 候选参考图并做最近邻像素放大后，为 6/8 和 4/4，但两个幼苗仍被自信误认。第二轮同时改变了参考图与缩放，且已看过第一轮结果，所以不能把提升全部归因于单一因素，也不是新盲测。

结论是优先使用可追踪的模板候选与确认流程，LLM 可以辅助比较和解释。现有证据不足以批准任意截图的无人确认识别。

## 检索与 mKG-RAG 的实测边界

| 方法 | 可回答题必要证据完整覆盖 | 平均必要事实召回 | 两个缺身份题正确要求补充 |
|---|---:|---:|---:|
| A 纯文字 | 7/14 | 61.9% | 0/2 |
| B 平面图文 | 10/14 | 86.9% | 2/2 |
| C 图文图谱粗排 | 5/14 | 60.1% | 2/2 |
| D 对 C 同候选重排 | 10/14 | 86.9% | 2/2 |

这是证据集合覆盖，不是最终回答准确率。所有方法仍可能返回无关证据；A 缺少图片的信息优势差异不能用来证明图结构有效。C/D 的候选池相同，D 的改进来自排序；D 与 B 持平，所以方法贡献目前“尚不明显”。完整逐题和 8 组配对见 `results/retrieval_scores.jsonl`、`results/retrieval_comparison.csv` 和 `results/retrieval_traces.jsonl`。

第一阶段最多 5 页；第二阶段最多检查 60 张卡、保留 40 张候选、最终 8 张卡和 4 张图、4000 个 Unicode 字符；图扩展最多 3 跳、30 个领域节点和 120 次领域边访问。最终实现把图遍历限制在候选页面及其可用事实范围，输出真实节点和边 ID。粗排曾在早期轮次得到 6/14，语义和页面约束审计后最终为 5/14；旧轮次没有覆盖删除，不能将最终结果当作未经查看的正式测试。

遗漏主要涉及浇水前提和加工时钟等跨页事实。生产原型允许显式补齐最多 12 个工具依赖，并在轨迹中列出；**该补查没有计入受控 D 的成绩**。R09/R10 用两个作物图标替代两种种子，R15/R16 用已确认作物与未识别原料替代明确/多义加工品，因此原合同中的这两组配对仍待补齐。页面/图片召回已附加计算，但来源/图像 gold 的独立审核、关系级召回和完整条件一致性评价仍欠缺。

论文方法映射和五种 Wiki 对齐案例见 `MKG_SEMANTICA.md`。本轮没有训练 QM-Retriever，没有安装 EGTR，也没有实施视觉向量编码器方案；不能称为完整复现 mKG-RAG。HTML 布局导入是当前领域适配的主要关系来源。

## 数据、版本、资源和复现记录

12 个 Wiki 页面修订为：Parsnip 191123；Parsnip Seeds 193542；Melon 193510；Melon Seeds 193509；Crops 193979；Keg 195253；Preserves Jar 195389；Bundles 195448；Blueberry 192090；Blueberry Seeds 193154；Wine 192625；Jellies and Pickles 191929。完整永久链接、抓取时间和 SHA-256 见 `data/source_manifest.jsonl`。

程序 HTTP 访问 Wiki 得到 403 后停止该路径。通过正常浏览器读取可访问的页面 DOM、使用浏览器资源导出得到小样；保存的是渲染后的文章 DOM，HTTP 状态没有被伪填为 200。外部截图共尝试 10 个地址，9 个成功，Twinfinite 图片返回 403 并保留失败记录。这不能证明未来可全自动、全量抓取。原始游戏图像许可尚未逐项核对，留本地研究使用，发布素材包前需清理。

本机 macOS 27.0、arm64、10 个逻辑 CPU，Python 3.12.14，Semantica 0.7.0；未使用 GPU 编码器或下载大模型权重。工作区未初始化 Git，因此使用文件哈希和独立 run_id 追踪，没有虚构提交号。最新离线运行 ID、耗时、代码/输入/产物哈希、阶段 stdout/stderr 和网络审计均在 `results/v08.json`，历次 manifest 另存于 `results/runs/`。

ChatECNU 地址和模型标识依据用户提供的配置及 [官方接口文档](https://developer.ecnu.edu.cn/vitepress/llm/index.html)。本次两个接口都接受了图片并正确描述整张背包截图；不据此推断模型内部实际厂商或版本。总共 34 次真实请求均获得 HTTP 200，六项文本/JSON/tool 参数校验通过，图片能力和细粒度效果分别记录。没有再次索要或输出密钥。默认 `ecnu-max` 用于文字与工具协调，`ecnu-plus` 图像输出受确认策略约束。

最重要的剩余事项与恢复动作见 `BLOCKERS.md`；开发范围决定见 `DECISION.md`。教师要求的最终 60 题、完整 Agent/网页、历史、图谱浏览和导出体验尚未开发，不属于这次已通过的核验成果。
