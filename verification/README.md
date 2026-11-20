# 星露谷助手可行性核验

本目录包含真实资料、可运行的核验原型和结果，不是完整网页应用。结论见 `REPORT.md`、`DECISION.md`；重点查看 `MKG_SEMANTICA.md`，其中展示 Semantica 与 mKG-RAG 工程适配的实际连接。原始核验合同保留在 `PLAN.md`，不足样本、版本和独立审核的项目仍标为 PARTIAL。

## 环境与配置

工作目录为 `.`。使用已配置的 `.venv/bin/python`（Python 3.12.14 / arm64），Semantica 固定为 0.7.0。系统 Python 未修改。依赖说明见 `ENVIRONMENT.md`，锁文件 `requirements/verification.lock.txt` 是本机 CPython 3.12 / macOS arm64 的带哈希锁定结果。

`.env` 是隐藏文件。Finder 中按 Command+Shift+G 输入其完整路径即可定位。ChatECNU 使用 `CHATECNU_BASE_URL`、`CHATECNU_MODEL`、`CHATECNU_VISION_MODEL`、`CHATECNU_API_KEY`、`CHATECNU_MAX_CALLS` 和 `CHATECNU_MAX_OUTPUT_TOKENS`。当前配置已由用户填写；程序不打印密钥、不保存请求头或模型隐藏推理。示例文件不含密钥，默认调用额度为 0。实际本轮上限 100 次、每次最多 1024 输出 token，计数保存在本地 `logs/api_budget.json`。

## 一条命令离线重新执行

在项目根目录运行：

```sh
.venv/bin/python -m verification.run_all --offline
```

它重新解析本地 Wiki 快照、真实构图与独立进程重载，重跑模板识别、A/B/C/D 检索、12 类计算、8 条端到端链和专门的 mKG-RAG × Semantica 检查。每个阶段在新进程中禁止网络；不安装依赖、不下载图片、不调用模型。在线模型的历史结果单独列为复用证据，不计成本轮新调用。

必须保留本地 `data/raw`、`data/assets`、`data/external`、`data/visual_crops` 和清单文件。图片因许可未清理而被 Git 忽略，所以一个只含代码的克隆并不自动拥有这些输入。缺原始文件时不能复现完整测试。浏览器 DOM 采集仍需人工辅助，不能把它称作已完成全自动抓取；HTTP 403 路径已停止。

退出码：0＝所选完整门槛全部满足；1＝必测断言失败；2＝没有核心断言失败，但完整验收有缺口；3＝配置或运行错误。**当前预期为 2**，原因是样本、版本、独立审核和研究评价尚未满足原计划，不是将 PARTIAL 当作 PASS。执行详情、代码/输入/输出哈希和各阶段网络审计记录写入 `results/runs/<run_id>/manifest.json`，最新汇总为 `results/v08.json`。

## 实际运行原型

种子截图加显式日期、数量和浇水条件：

```sh
.venv/bin/python -m verification.cli \
  --image verification/data/visual_crops/V28.png \
  --intent planting --day 23 --plants 50 --season Spring --watered \
  --output verification/artifacts/demo_seed.json
```

阶段截图先返回候选；确认后计算区间：

```sh
.venv/bin/python -m verification.cli \
  --image verification/data/visual_crops/V33.png \
  --intent remaining --watered --confirmed-entity Melon_Stage_3 \
  --output verification/artifacts/demo_stage.json
```

所有阶段当前都要求确认。原型接收已裁剪的单个对象，不实现整屏自动框选、数量/品质 OCR 或自动读取游戏存档。计算输出是冻结 Wiki 快照下的技术诊断，不能视为已经完成指定游戏版本的发布验收。

## 分项命令

| 内容 | 命令 |
|---|---|
| 真实资料抽取 | `.venv/bin/python -m verification.knowledge` |
| Semantica 构图、导出、来源、独立重载 | `.venv/bin/python -m verification.graph` |
| 模板视觉小样 | `.venv/bin/python -m verification.vision` |
| 检索对照 | `.venv/bin/python -m verification.retrieval` |
| 计算及隔离干预 | `.venv/bin/python -m verification.probes.calculation_probe` |
| 两正向六异常链 | `.venv/bin/python -m verification.pipeline` |
| mKG-RAG × Semantica 专项 | `.venv/bin/python -m verification.probes.mkgrag_semantica_probe` |
| 在线模型接口 8 项 | `.venv/bin/python -m verification.chatecnu` |
| 在线直接识图 12 项和工具链 2 次调用 | `.venv/bin/python -m verification.probes.model_workflow_probe` |
| 在线候选参考图辅助识别 12 项 | `.venv/bin/python -m verification.probes.model_reference_probe` |

后三项会发送公开图片或核验任务到已配置的 ChatECNU，受本地调用计数限制；不会由离线命令自动启动。HTTP 401/403/429 时探测停止，失败记录不通过换身份或无限重试覆盖。

`visual_data.py` 和 `retrieval_data.py` 是数据集构造脚本，日常复跑读取已冻结清单，不重新挑图、改题或更换 gold。原始第一轮结果、审计修正和阶段确认策略修订前的结果分别保留在 `results/rounds/` 与历次运行目录；本轮最终结果已经经过测试集查看和工程修正，不能宣传为从未观察过的正式盲测。
