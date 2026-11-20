# 鹈鹕镇助手

鹈鹕镇助手为《星露谷物语》玩家回答 Wiki 知识、作物与物品辨认、售价计算及加工比较等问题。mKG-RAG 的多模态方法将 Wiki 文本、图像局部观测和实体关系对齐，Semantica 负责构图和记录来源。单个 Agent 根据用户目标选择检索、澄清和计算工具，给出带证据的答案。

## 离线试用

在仓库根目录运行以下命令。依赖锁经过 CPython 3.12 与 macOS arm64 环境验证。安装依赖后，以下检查可离线执行。

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements/verification.lock.txt
.venv/bin/python -m stardew_agent --help
.venv/bin/python -m pytest -q tests/test_answer_rendering.py
```

公开仓库包含后端、网页工作台、建图和采集脚本、工程测试、评测协议及 Wiki 来源与图片哈希清单。上述测试使用自带的样例覆盖库存预留、不同数量的加工方案和新实体的答案展示。

## 完整工作台

完整图谱、历史对话、游戏截图、原始 Wiki 文件及模型响应保存在开发机。复现完整流程需要根据 `data/manifests/` 自行取得对应版本的网页与资源，运行建图后才能查询候选图谱。历史日志和完整样例回放依赖当时的冻结资料。仓库中的开发报告保留了相应本地产物的路径与统计。

`verification.acquire` 可以抓取一小批公开 Wiki 页面。`configs/corpus.json` 和 `stardew_agent.cli` 定义了建库批次与代理入口。获取来源和快照后，如需在线模型，在本地从 `.env.example` 创建 `.env`，填写自己的 ChatECNU 密钥、可用模型与调用上限，随后运行工作台。

```sh
.venv/bin/python -m verification.acquire --help
.venv/bin/python -m stardew_agent serve --host 127.0.0.1 --port 8765
```

浏览器打开 <http://127.0.0.1:8765/>。网页提供对话、图片局部框选、来源审核和知识图谱探索。

## 当前进展

2026 年 11 月 18 日的本地候选图谱记录了 26 个来源页面、177 个实体、212 条事实、250 条关系与 817 条候选图文对齐。开发机记录了 270 项通过的工程测试。正式知识审批、独立视觉评测和金标准审批尚待完成。开放加工比较中仍出现了只交付一种方案的情况。

- [图谱结构与 mKG-RAG、Semantica 的分工](docs/v3/POST_MIDTERM_GRAPH_STATUS.md)
- [Agent 运行结果与开发状态](docs/v3/POST_MIDTERM_STATUS.md)
- [逐题评测与限制](docs/v3/POST_MIDTERM_EVALUATION_NOTES.md)
- [扩大图谱前的开发与验收计划](docs/v3/PRE_EXPANSION_PLAN.md)
- [后续开发总计划](docs/v3/POST_MIDTERM_DEVELOPMENT_PLAN.md)
