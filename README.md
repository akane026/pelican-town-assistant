# 鹈鹕镇助手

鹈鹕镇助手为《星露谷物语》玩家回答 Wiki 知识、作物与物品辨认、售价计算及加工比较等问题。mKG-RAG 的多模态方法将 Wiki 文本、图像局部观测和实体关系对齐，Semantica 负责构图和记录来源。单个 Agent 根据用户目标选择检索、澄清和计算工具，给出带证据的答案。

## React 前端（Windows / macOS）

前端已整体迁移到 **React + TypeScript + Vite**，包含农场助手、物品图谱、我的计划、知识管理，以及设置弹窗和证据抽屉。图谱使用 React Flow，基础组件使用 shadcn/ui + Radix，接口缓存与任务轮询使用 TanStack Query。桌面、平板和手机使用同一套响应式页面。

安装 Node.js 24 LTS。在仓库根目录执行以下通用命令：

```sh
npm --prefix web ci
npm --prefix web run build
```

完成下文 Python 环境安装后，启动本机工作台：

Windows（PowerShell）：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m stardew_agent serve --host 127.0.0.1 --port 8766
```

macOS：

```sh
.venv/bin/python -m stardew_agent serve --host 127.0.0.1 --port 8766
```

打开 <http://127.0.0.1:8766/>。Python 同时提供 `web/dist` 中的 React 构建产物和 `/api` 接口，刷新子页面也可正常访问。`web/index.html` 仅是 React 挂载入口，原有原生 HTML 页面、`app.js` 和旧样式已移除。修改前端代码后需重新运行 build。

开发时保留上述后端，在另一个终端运行：

```sh
npm --prefix web run dev
```

打开 <http://127.0.0.1:5173/>，修改代码后自动刷新。Vite 默认将 `/api` 转发至 `127.0.0.1:8766`；如使用其他后端端口，在启动 Vite 前设置 `PELICAN_BACKEND_URL`。代理只用于本机开发，后端的同源检查和 CSRF 校验仍然启用。终端按 `Ctrl+C` 停止对应服务。

没有知识快照时可以查看页面、设置和明确标注的图谱交互示例；真实问答、图片识别与知识审核需要先准备资料。图谱示例不写入知识库，也不会作为 Agent 的回答依据。

前端目录、接口约定和测试方式见 [前端开发说明](web/README.md)。

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

### 知识库浏览

左侧「知识库浏览」打开 `/library`，支持文件上传、网页导入、按名称或正文搜索、类型筛选、分页、正文/原始内容预览、修改和删除。当前一份文件或网页是一条独立资料；文件支持 UTF-8 编码的 TXT、Markdown、HTML、JSON、CSV，单份最多 2 MB。网页导入支持公开 HTTPS HTML/文本页面，保存当时的副本；不执行脚本、不登录网站、不访问内网，访问受限时可以上传已保存的 HTML。PDF、Word 尚无解析器。

资料及其正文保存在后端 `data/library/library.sqlite3`，与浏览器无关。数据库在启动时自动创建。编辑采用版本号检查，防止多个页面互相覆盖；删除只移除资料库中的副本，不会破坏既有 `data/snapshots/`、证据链或历史对话。

**上传与构图是两步。** 本页是原文管理入口，上传状态为「待构图」，尚未自动接入问答；现有 Wiki 构建流程仍需准备 `data/manifests/` 对应的来源与资源后执行 ingest / build / snapshot。普通文本不是已验证的图谱事实。页面不提供启用/停用开关：当前图谱包含跨来源合并和派生关系，改变来源集合需要重新生成快照。Agent 每轮读取对话绑定的快照，按任务调用检索工具，可能多次检索；不会每问一次重新构图，旧对话也不会自动切换到新快照。

接口：`GET /api/library?q=&kind=&offset=`、`GET /api/library/source?id=`，以及 `POST /api/library/create`、`/api/library/update`、`/api/library/delete`。写请求使用现有同源与 CSRF 校验，不需要模型密钥；更改和删除携带 `id`、`revision`。上传文件以 `kind=file`、`filename`、base64 `data` 提交；网页以 `kind=web`、`url` 提交，均可选填 `title`。

完整图谱、历史对话、游戏截图、原始 Wiki 文件及模型响应保存在开发机。复现完整流程需要根据 `data/manifests/` 自行取得对应版本的网页与资源，运行建图后才能查询候选图谱。历史日志和完整样例回放依赖当时的冻结资料。仓库中的开发报告保留了相应本地产物的路径与统计。

`verification.acquire` 可以抓取一小批公开 Wiki 页面。`configs/corpus.json` 和 `stardew_agent.cli` 定义了建库批次与代理入口。获取来源和快照后，如需在线模型，在本地从 `.env.example` 创建 `.env`，设置可用模型与调用上限，随后运行工作台。网页使用的密钥由用户在浏览器内填写。

Windows（PowerShell；仅在 `.env` 不存在时复制，避免覆盖已有配置）：

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

macOS：

```sh
cp -n .env.example .env
```

编辑 `.env` 中的 `CHATECNU_MODEL`、`CHATECNU_VISION_MODEL` 和 `CHATECNU_MAX_CALLS`，保持 `CHATECNU_API_KEY` 为空。模板调用上限为 `0`，默认禁止模型调用；请设置自己的额度。首次打开网页会显示「设置 → 连接与隐私」，填写自己的 ChatECNU API 密钥即可保存到浏览器本地存储（localStorage）。刷新或重新打开同一地址后自动恢复，也可以在设置中更换或清除；密钥不会写入 `.env`、任务记录或日志。同一浏览器与地址的标签页共享已保存的密钥，不同浏览器、端口和设备不会自动同步。清除网站数据也会删除密钥。每次提问由本机后端临时使用请求携带的密钥，不回退到 `.env` 密钥。保存密钥不会发起模型调用；清除不会中断已经提交的请求。准备好有效知识快照后再使用真实问答；仅复制配置文件并不会自动下载或建立知识库。

Windows（PowerShell）：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m verification.acquire --help
.\.venv\Scripts\python.exe -X utf8 -m stardew_agent serve --host 127.0.0.1 --port 8766
```

macOS：

```sh
.venv/bin/python -m verification.acquire --help
.venv/bin/python -m stardew_agent serve --host 127.0.0.1 --port 8766
```

浏览器打开 <http://127.0.0.1:8766/>。网页提供对话、图片局部框选、来源审核和知识图谱探索。

先按上文构建 React 前端，再启动后端。开发预览使用 5173，后端使用 8766；终端按 `Ctrl+C` 停止服务。

## 当前进展

模型运行时的职责拆分、面试追问和当前验证边界见 [架构与面试准备](docs/INTERVIEW_ARCHITECTURE.md)。`ModelClient` 支持注入模型客户端；生产模型调用不再通过修改实验模块的全局目录来隔离日志。

2026 年 11 月 18 日的本地候选图谱记录了 26 个来源页面、177 个实体、212 条事实、250 条关系与 817 条候选图文对齐。开发机记录了 270 项通过的工程测试。正式知识审批、独立视觉评测和金标准审批尚待完成。开放加工比较中仍出现了只交付一种方案的情况。

- [图谱结构与 mKG-RAG、Semantica 的分工](docs/v3/POST_MIDTERM_GRAPH_STATUS.md)
- [Agent 运行结果与开发状态](docs/v3/POST_MIDTERM_STATUS.md)
- [逐题评测与限制](docs/v3/POST_MIDTERM_EVALUATION_NOTES.md)
- [扩大图谱前的开发与验收计划](docs/v3/PRE_EXPANSION_PLAN.md)
- [后续开发总计划](docs/v3/POST_MIDTERM_DEVELOPMENT_PLAN.md)
