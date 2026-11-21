# 鹈鹕镇助手

鹈鹕镇助手为《星露谷物语》玩家回答 Wiki 知识、作物与物品辨认、售价计算及加工比较等问题。mKG-RAG 的多模态方法将 Wiki 文本、图像局部观测和实体关系对齐，Semantica 负责构图和记录来源。单个 Agent 根据用户目标选择检索、澄清和计算工具，给出带证据的答案。

## Windows / macOS 前端预览

仅查看页面布局时，无需安装项目依赖、配置 API 或准备知识快照。在仓库根目录打开终端运行：

Windows（PowerShell，已安装 Python）：

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory web
```

macOS：

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory web
```

浏览器打开 <http://127.0.0.1:8765/>，可查看助手对话、建库审阅、知识探索和运行记录四个页面的布局。静态预览不提供 `/api/` 接口，因此会提示加载失败，聊天、检索、审核和真实数据展示不可用。终端按 `Ctrl+C` 停止服务。若端口已被占用，可将 `8765` 换为 `8766`，并修改访问地址。

## 安装与离线检查（Windows / macOS）

使用 Python 3.12。Windows 命令中的 `-X utf8` 也为第三方库及旧评测脚本启用 UTF-8，避免系统默认 GBK 编码影响中文资料。后端使用跨平台 `filelock` 文件锁，项目文本与 JSON 文件显式使用 UTF-8，Windows 原生运行无需 WSL。

Windows（PowerShell）：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -X utf8 -m pip install -r requirements/verification.in
.\.venv\Scripts\python.exe -X utf8 -m stardew_agent --help
.\.venv\Scripts\python.exe -X utf8 -m pytest -q tests/test_platform_compatibility.py tests/test_answer_rendering.py
```

macOS：

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements/verification.lock.txt
.venv/bin/python -m stardew_agent --help
.venv/bin/python -m pytest -q tests/test_platform_compatibility.py tests/test_answer_rendering.py
```

`verification.lock.txt` 是原 CPython 3.12 / macOS arm64 环境的依赖锁，并补充了跨平台锁依赖；其中部分包的哈希仅对应 macOS 安装包，Windows 使用 `verification.in` 安装。Windows 解析得到的依赖版本与 macOS 锁文件不保证一致。以上离线测试不调用模型，也不要求完整知识快照；完整测试集中的其他测试可能需要开发机资料。

公开仓库包含后端、网页工作台、建图和采集脚本、工程测试、评测协议及 Wiki 来源与图片哈希清单。上述测试使用自带的样例覆盖库存预留、不同数量的加工方案和新实体的答案展示。

## 完整工作台（Windows / macOS）

完整图谱、历史对话、游戏截图、原始 Wiki 文件及模型响应保存在开发机。复现完整流程需要根据 `data/manifests/` 自行取得对应版本的网页与资源，运行建图后才能查询候选图谱。历史日志和完整样例回放依赖当时的冻结资料。仓库中的开发报告保留了相应本地产物的路径与统计。

`verification.acquire` 可以抓取一小批公开 Wiki 页面。`configs/corpus.json` 和 `stardew_agent.cli` 定义了建库批次与代理入口。获取来源和快照后，如需在线模型，在本地从 `.env.example` 创建 `.env`，填写自己的 ChatECNU 密钥、可用模型与调用上限，随后运行工作台。

Windows（PowerShell；仅在 `.env` 不存在时复制，避免覆盖已有密钥）：

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

macOS：

```sh
cp -n .env.example .env
```

编辑 `.env` 中的 `CHATECNU_API_KEY`、`CHATECNU_MODEL`、`CHATECNU_VISION_MODEL` 和 `CHATECNU_MAX_CALLS`。模板调用上限为 `0`，默认禁止模型调用；请设置自己的额度。密钥仅在后端配置，不在网页填写。准备好有效知识快照后再启动服务；仅复制配置文件并不会自动下载或建立知识库。

Windows（PowerShell）：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m verification.acquire --help
.\.venv\Scripts\python.exe -X utf8 -m stardew_agent serve --host 127.0.0.1 --port 8765
```

macOS：

```sh
.venv/bin/python -m verification.acquire --help
.venv/bin/python -m stardew_agent serve --host 127.0.0.1 --port 8765
```

浏览器打开 <http://127.0.0.1:8765/>。网页提供对话、图片局部框选、来源审核和知识图谱探索。

完整服务与静态预览使用相同端口，请先停止预览服务再启动后端。终端按 `Ctrl+C` 停止服务。

## 当前进展

模型运行时的职责拆分、面试追问和当前验证边界见 [架构与面试准备](docs/INTERVIEW_ARCHITECTURE.md)。`ModelClient` 支持注入模型客户端；生产模型调用不再通过修改实验模块的全局目录来隔离日志。

2026 年 11 月 18 日的本地候选图谱记录了 26 个来源页面、177 个实体、212 条事实、250 条关系与 817 条候选图文对齐。开发机记录了 270 项通过的工程测试。正式知识审批、独立视觉评测和金标准审批尚待完成。开放加工比较中仍出现了只交付一种方案的情况。

- [图谱结构与 mKG-RAG、Semantica 的分工](docs/v3/POST_MIDTERM_GRAPH_STATUS.md)
- [Agent 运行结果与开发状态](docs/v3/POST_MIDTERM_STATUS.md)
- [逐题评测与限制](docs/v3/POST_MIDTERM_EVALUATION_NOTES.md)
- [扩大图谱前的开发与验收计划](docs/v3/PRE_EXPANSION_PLAN.md)
- [后续开发总计划](docs/v3/POST_MIDTERM_DEVELOPMENT_PLAN.md)
