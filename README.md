# 鹈鹕镇助手

面向《星露谷物语》玩家的本机知识助手，支持资料查询、物品关系探索、截图物品辨认，以及售价和加工方案比较。回答结合 Wiki 原文、图片证据、知识图谱与计算工具，提供可追溯的依据。

前端使用 React、TypeScript 和 Vite，界面沿用星露谷的像素与农场风格；Python 后端提供 API、知识构建和 Agent 工具调用。项目支持 Windows 原生运行，无需 WSL，也支持 macOS。

## 目录

- [1. 环境准备](#1-环境准备)
- [2. 安装与首次配置](#2-安装与首次配置)
- [3. 日常启动与登录](#3-日常启动与登录)
- [4. 页面与账号权限](#4-页面与账号权限)
- [5. 知识资料与审核流程](#5-知识资料与审核流程)
- [6. 数据保存位置](#6-数据保存位置)
- [7. 开发与测试](#7-开发与测试)
- [8. 项目结构与技术路线](#8-项目结构与技术路线)
- [9. 常见问题](#9-常见问题)
- [10. 当前边界与进一步阅读](#10-当前边界与进一步阅读)

## 1. 环境准备

| 环境 | 版本或要求 |
| --- | --- |
| Python | 3.12 |
| Node.js | 建议使用 24 LTS，包含 npm |
| 终端 | Windows PowerShell 或 macOS 终端 |
| 浏览器 | 支持现代 Web 标准的浏览器 |

打开终端并进入项目根目录 `pelican-town-assistant`。下文所有命令均在该目录执行，除非另有说明。

项目有两个运行层次：

- **界面体验**：安装依赖、构建前端并启动服务后，即可注册、登录、管理资料和查看图谱交互示例。
- **真实问答**：还需要有效的知识快照、原文与图片资源，以及可用的模型配置、个人 API 密钥和调用额度。

仓库中的清单与历史报告不等于已经恢复了本机知识库。首次运行没有知识快照时，页面会提示知识尚未准备好。

## 2. 安装与首次配置

### 2.1 创建 Python 环境并安装依赖

Windows（PowerShell）：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -X utf8 -m pip install -r requirements/verification.in
```

macOS：

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements/verification.in
```

以上使用直接依赖清单安装。仓库另有 `requirements/verification.lock.txt`，用于原 CPython 3.12 / macOS arm64 环境的依赖复现；部分哈希仅对应该平台，不应直接作为 Windows 安装命令。使用直接依赖清单时，解析得到的间接依赖版本可能与历史锁文件不同。

Windows 命令中的 `-X utf8` 用于避免中文资料受到系统默认编码影响。后续命令直接指定虚拟环境中的 Python，无需先激活虚拟环境。

### 2.2 安装并构建前端

Windows 和 macOS 使用相同命令：

```sh
npm --prefix web ci
npm --prefix web run build
```

构建结果保存在 `web/dist`，由 Python 服务直接提供。日常使用不需要单独启动 Node.js 服务。

### 2.3 创建管理员（维护者只需执行一次）

如果需要维护知识库的审核与发布，请先创建管理员账号。仅体验普通用户功能时，可以在网页直接注册。

Windows：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m stardew_agent create-admin --username admin
```

macOS：

```sh
.venv/bin/python -m stardew_agent create-admin --username admin
```

`admin` 是账号名称，可以替换。命令会提示输入并确认密码，输入时不显示字符。

- 用户名：3–32 个字符，可包含字母、数字、汉字、下划线或连字符。
- 密码：6–128 个字符，以加盐哈希形式保存。
- 没有默认管理员密码；已有管理员后，命令会拒绝重复初始化，不会覆盖账号或重置密码。

### 2.4 配置模型（使用真实问答前完成）

先从模板创建 `.env`，保留已有文件。

Windows：

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

macOS：

```sh
if [ ! -f .env ]; then cp .env.example .env; fi
```

根据实际可用服务编辑以下配置：

| 配置项 | 用途 |
| --- | --- |
| `CHATECNU_BASE_URL` | ChatECNU 接口地址 |
| `CHATECNU_MODEL` | 文本与 Agent 使用的模型名称 |
| `CHATECNU_VISION_MODEL` | 视觉模型名称 |
| `CHATECNU_MAX_CALLS` | 模型累计调用上限；模板为 `0`，默认禁止调用 |
| `CHATECNU_MAX_OUTPUT_TOKENS` | 模型输出预算，调用时可能按具体任务覆盖 |
| `SDV_GAME_VERSION`、`SDV_PLATFORM`、`SDV_MODDED` | 已确认的游戏版本、平台及模组信息 |

模型名称与地址以你实际可用的服务为准。自行设置允许的调用上限；一次问答可能多次调用模型，上限不是每个问题都重新计算的次数。

**网页使用的 `CHATECNU_API_KEY` 保持为空。** 启动并登录后，在侧栏底部点击头像，选择「设置 → 模型连接」，填写自己的 API 密钥。CLI 在线建库使用独立的本地模型配置，不会自动取得浏览器里的密钥。

## 3. 日常启动与登录

完成安装后，每次使用项目只需运行服务命令。

Windows：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m stardew_agent serve --host 127.0.0.1 --port 8766
```

macOS：

```sh
.venv/bin/python -m stardew_agent serve --host 127.0.0.1 --port 8766
```

手动打开 **<http://127.0.0.1:8766/>**，使用已有账号登录，或点击「注册」创建普通用户。管理员也使用同一个登录表单，后端根据账号角色分配权限。

Python 服务同时提供 `web/dist` 中的前端和 `/api` 接口，不会自动打开浏览器，也不会自动构建前端或知识图谱。启动时会创建缺少的数据库表，保留已有账号、密码和资料；无需重复执行 `create-admin`。

在运行服务的终端按 `Ctrl+C` 停止。修改后端代码或 `.env` 后需重启服务；修改前端代码后的处理方式见[开发与测试](#7-开发与测试)。

## 4. 页面与账号权限

| 入口 | 主要功能 | 可见范围 |
| --- | --- | --- |
| 农场助手 | 提问、上传截图、补充条件、查看答案来源与计算记录 | 所有登录用户 |
| 物品图谱 | 搜索实体、查看关系、筛选、切换列表与查看证据 | 所有登录用户 |
| 知识资料 | 上传文件、导入网页、搜索、预览、编辑与删除 | 所有登录用户 |
| 我的计划 | 保存回答与当时条件，比较方案副本 | 所有登录用户 |
| 审核与发布 | 核对知识与规则、发布审核后的知识、查看评测记录 | 仅管理员 |
| 头像菜单 | 设置、查看账户、退出登录 | 所有登录用户 |

网页注册始终创建普通用户，不能自行选择管理员身份。权限同时在后端校验，直接输入审核页面地址或调用接口无法取得管理员权限。

知识资料共享浏览，修改与删除仅允许上传者本人或管理员执行。普通用户只能访问自己的对话；管理员可访问现有对话。原有未记录归属的对话和资料由管理员管理。计划是保存时的回答副本，不会自动重新计算。

## 5. 知识资料与审核流程

### 5.1 上传和浏览原文

在「知识资料」中点击「添加资料」。每份文件或网页作为一条独立资料保存。

| 方式 | 支持范围 |
| --- | --- |
| 文件上传 | UTF-8 编码的 TXT、Markdown、HTML、JSON、CSV，单份最多 2 MB |
| 网页导入 | 公开 HTTPS HTML 或文本网页，保存导入当时的内容副本 |

目前不支持直接解析 PDF、Word；网页导入不登录网站、不执行页面脚本，不读取内网地址或依赖脚本加载的正文。网站访问受限时，可上传已保存的 HTML。

可以查看正文与原始内容、搜索、修改或删除本地副本。编辑与删除带有版本检查，防止多页面相互覆盖。

### 5.2 从资料构建知识快照（维护者）

**当前上传与构图尚未自动接通。** 上传成功后显示「待构图」，不会立即进入 Agent 的问答依据，也不会自动替换既有知识。现有构建流程需要维护者将资料转换为项目使用的来源与资源清单。

完整流程为：

```text
准备原文与图片 → 登记来源清单 → 抽取与构图 → 候选快照 → 人工审核 → 正式发布
```

1. 按 `data/manifests/sources.json`、`assets.json` 恢复或登记资料，保证路径、内容哈希和图片资源匹配。取得的新版网页不能直接冒充清单中固定的旧版内容。
2. 在 `configs/corpus.json` 中确认构建批次，再执行校验和构建。
3. 使用构建返回的 `build_id` 生成候选快照。
4. 管理员登录工作台，在「审核与发布」核对知识、规则及其依据，填写理由后批准、拒绝或暂缓。
5. 发布通过审核且依赖完整的知识子集；候选快照和历史版本保留。

以下为**资料已经准备完整后**的结构构建示例，不调用模型，也不代表已完成多模态语义验证。将 `BUILD_ID` 替换为 `build` 命令实际返回的值。

Windows：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m stardew_agent ingest
.\.venv\Scripts\python.exe -X utf8 -m stardew_agent build --batch development --mode structural --offline --resume
.\.venv\Scripts\python.exe -X utf8 -m stardew_agent snapshot --build-id BUILD_ID
```

macOS：

```sh
.venv/bin/python -m stardew_agent ingest
.venv/bin/python -m stardew_agent build --batch development --mode structural --offline --resume
.venv/bin/python -m stardew_agent snapshot --build-id BUILD_ID
```

检查构建输出中的状态和失败清单，资料不完整或构建部分失败时先修复问题。多模态构建、批次扩展与验收安排见[扩大图谱前的开发与验收计划](docs/v3/PRE_EXPANSION_PLAN.md)。`verification.acquire` 是早期公开 Wiki 采集工具，其产物也需要整理后才能进入当前清单；使用方法见 [verification/README.md](verification/README.md)。

### 5.3 审核、冲突与版本

程序检查数据结构、引用、资源对应和部分事实冲突；管理员对照原文、表格和图片，核对实体、数值、单位、适用条件和版本。自动检查通过或模型认同，不等于已经完成人工审核。

同一实体、属性和条件下出现不同值或单位时，构建程序会标记冲突，阻止相关事实直接正式发布。目前没有完整的冲突裁决页面，需要维护者修正来源、条件或抽取结果后重新构建。

Agent 按问题调用检索、澄清和计算工具，一轮可能多次检索，但不会每问一次就重新构图。每个对话绑定自己的知识快照，旧对话不会自动切换新版本。改变知识来源集合需要重新构建，因此当前不提供资料启用／停用开关。

## 6. 数据保存位置

| 数据 | 位置与行为 |
| --- | --- |
| 账号、会话、资源归属 | 后端 `data/library/library.sqlite3`，分别使用 `users`、`sessions`、`resource_owners` 表 |
| 上传文件与网页正文 | 同一数据库的 `library_sources` 表 |
| 对话、任务状态与事件 | 后端 `data/runtime/tasks.sqlite3` |
| 知识快照与审核记录 | `data/snapshots/`、`data/reviews/`，运行后按需生成 |
| 当前知识版本指针 | `data/latest_candidate.json`、`data/current.json` |
| 上传截图 | 后端 `data/uploads/` |
| 构建、模型和评测产物 | `artifacts/v3/` 等本机目录 |
| 个人 API 密钥 | 浏览器 localStorage，按账号区分 |
| 我的计划 | 浏览器 localStorage，按账号区分 |

API 密钥刷新后仍可恢复，只在发起问答时交给本机后端临时使用，不写入任务记录或 `.env`。设置中的「清除密钥」可删除当前账号保存的密钥。不同浏览器、访问地址、端口和设备的浏览器数据不会自动同步；清除网站数据会移除本地密钥和计划。旧的未区分账号的浏览器数据不会自动迁移。

登录使用有效期七天的 HttpOnly、SameSite=Strict Cookie，退出后服务端会话失效。项目当前仅监听本机地址，账号系统不会自动将服务开放到互联网。

删除知识资料只删除原文管理中的副本，不能撤回已生成的知识快照，也不会删除历史对话；如需更新问答知识，应重新构建和发布。数据库和运行目录包含本机数据，备份时应停止服务并保留所需数据库、快照与资源文件。

## 7. 开发与测试

### 前端开发

先按[日常启动](#3-日常启动与登录)运行 Python 后端，再打开另一个终端：

```sh
npm --prefix web run dev
```

访问 <http://127.0.0.1:5173/>，修改 React 代码后自动刷新。Vite 默认把 `/api` 代理到 `127.0.0.1:8766`。后端换端口时，在启动 Vite 前设置 `PELICAN_BACKEND_URL`。

日常使用的 `8766` 页面读取静态构建结果。修改前端后，执行以下命令并刷新该页面：

```sh
npm --prefix web run build
```

前端检查命令：

```sh
npm --prefix web run typecheck
npm --prefix web test
npm --prefix web run format:check
```

组件职责、目录与代理说明见 [web/README.md](web/README.md)。

### 后端测试

以下测试不需要在线模型或完整知识快照，适合安装后的基础检查。

Windows：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q tests/test_auth.py tests/test_frontend_serving.py tests/test_platform_compatibility.py tests/test_answer_rendering.py
```

macOS：

```sh
.venv/bin/python -m pytest -q tests/test_auth.py tests/test_frontend_serving.py tests/test_platform_compatibility.py tests/test_answer_rendering.py
```

完整工程测试中的部分用例和历史回放依赖开发机资料。网页及离线测试通过，不代表真实模型问答、视觉识别或正式知识已经验收。

## 8. 项目结构与技术路线

```text
pelican-town-assistant/
├── stardew_agent/       Python 后端、认证、Agent、检索、规则与知识构建
├── web/
│   ├── src/            React 页面、组件、接口与样式
│   ├── public/         Logo、登录图片等静态资源
│   └── dist/           前端构建产物，由 Python 提供
├── configs/            建库批次、别名与配置
├── data/               来源清单、本机数据库、截图和知识快照
├── requirements/       Python 依赖清单与历史环境锁文件
├── tests/              后端工程测试
├── evaluation/         评测协议与本机结果
├── verification/       早期采集与可行性验证工具
├── artifacts/          本机运行与构建产物
└── docs/               架构、研究与开发记录
```

前端使用 React Flow 展示关系网络，Dagre 负责布局，Radix／shadcn 组件提供基础交互，TanStack Query 管理请求和轮询。后端采用动态单 Agent，根据任务选择检索、图像候选、条件澄清和计算工具。

知识链采用 mKG-RAG 的图文对齐思路；领域适配层负责抽取、规范化和校验，Semantica 参与构图、持久化与来源管理。计算由规则工具执行，结果绑定任务版本和知识快照。架构细节见[架构与面试准备](docs/INTERVIEW_ARCHITECTURE.md)。

## 9. 常见问题

| 问题 | 处理方式 |
| --- | --- |
| 每次启动都要创建管理员吗？ | 不需要。`create-admin` 只初始化首个管理员，日常只运行 `serve` |
| 启动会重置数据库吗？ | 不会。只创建缺少的表，保留已有账号和资料 |
| 页面提示前端尚未构建 | 执行 `npm --prefix web ci` 和 `npm --prefix web run build` |
| 改了前端代码但页面没变化 | 使用 Vite 开发服务，或重新构建后刷新 `8766` 页面 |
| 能登录，但无法真实问答 | 检查知识快照、原文资源、个人密钥、模型名称和调用上限 |
| 上传资料后仍然回答不了相关问题 | 上传不等于构图；需要维护者构建候选快照、审核和发布 |
| 图谱里只有交互示例 | 示例数据不属于当前知识库，也不作为回答依据；先准备真实快照 |
| 普通用户看不到审核入口 | 属于正常权限限制，使用管理员账号登录后查看 |
| 切换到 5173 后密钥或计划没了 | 浏览器存储按地址和端口隔离，开发页面与日常页面不共享这些数据 |
| 端口被占用 | 停止已有服务，或更换 `--port`；开发时同步调整代理目标 |

## 10. 当前边界与进一步阅读

目前已具备登录与角色权限、React 工作台、资料管理、图谱交互、知识构建和 Agent 工具链。资料上传到自动构图的页面流程、完整冲突裁决界面、PDF／Word 解析尚未接入；真实问答和图片识别依赖有效资料、模型与额度。项目不读取或修改游戏存档。

历史开发报告记录过 2026 年 11 月 18 日候选图谱的规模与工程测试结果，这些属于当时开发机的状态，不代表当前安装已经拥有相同数据，也不替代正式审核与独立评测。

- [图谱结构与 mKG-RAG、Semantica 的分工](docs/v3/POST_MIDTERM_GRAPH_STATUS.md)
- [Agent 运行结果与开发状态](docs/v3/POST_MIDTERM_STATUS.md)
- [逐题评测与限制](docs/v3/POST_MIDTERM_EVALUATION_NOTES.md)
- [扩大图谱前的开发与验收计划](docs/v3/PRE_EXPANSION_PLAN.md)
- [后续开发总计划](docs/v3/POST_MIDTERM_DEVELOPMENT_PLAN.md)
- [登录图片来源](web/public/images/SOURCES.md)
