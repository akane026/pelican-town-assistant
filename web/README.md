# 前端开发说明

这是本机 Python 工作台的 React 客户端。`index.html` 只挂载 `src/main.tsx`，业务界面全部由 React 组件渲染。

## 启动与检查

建议使用 Node.js 24 LTS。Windows PowerShell 和 macOS 终端使用相同命令：

```sh
npm ci
npm run dev
npm run typecheck
npm test
npm run build
npm run format:check
```

开发服务器为 `http://127.0.0.1:5173`，API 默认代理到 `http://127.0.0.1:8766`。后端启动方式见根目录 README。生产使用 Python 直接托管 `dist`，不需要运行 Node 服务。`npm run preview` 仅用于静态构建预览，不提供 API。

## 目录与职责

```text
src/
  main.tsx                    React、路由、请求缓存入口
  App.tsx                     主布局、导航、按需加载页面
  pages/
    chat-page.tsx             提问、轮询、答案、证据与导出
    graph-page.tsx            React Flow 画布、搜索、关系筛选、列表
    plans-page.tsx            方案副本、本地持久化、并排对照
    knowledge-page.tsx        来源、审核、发布与评测
    library-page.tsx          知识资料列表、搜索、预览、编辑和删除
  components/
    ui/                      shadcn/ui 生成的 Button / Dialog / Tabs
    feedback.tsx             加载、错误、空状态与操作反馈
    settings.tsx             任务模式与游戏条件
    image-inspector.tsx      上传图片的区域选择、候选确认
    library-import.tsx        文件与公开网页导入弹窗
    record-detail.tsx        原文、图片与来源详情
    pixel-art.tsx            项目原创 SVG 小图标
  hooks/use-workbench.ts      bootstrap、任务请求与轮询失效
  lib/
    api.ts                   fetch、CSRF、错误翻译与 URL 构建
    types.ts                 后端接口类型
    graph.ts                 Dagre 布局、关系配色、隔离的交互示例
    plans.ts                 带版本号的浏览器存储
    format.ts                中文标签和显示格式
  styles.css                 色彩变量、组件样式、响应式断点
```

修改页面逻辑优先进入对应 `pages` 文件；复用交互进入 `components`；接口字段变动先更新 `types.ts`。不要在组件中散落服务器地址、密钥或直接修改 DOM。图谱与 Markdown 等较重模块随页面按需加载。

## 数据约定

- `/api/bootstrap` 是初始化入口，缺少快照时仍正常渲染；POST 必须带会话 CSRF。
- 每个任务绑定自己的 `snapshot_id` 和 `revision`。来源、图谱、图片等任务相关查询携带 `task_id`，不能用最新候选知识替代历史任务来源。
- 任务运行时每 1.2 秒刷新，结束后停止轮询。切换任务使用独立缓存键与取消信号，避免把旧请求显示到新任务。
- 图谱中的节点和边保留后端 ID；点击边按该 ID 读取真实证据。搜索范围受已导入知识限制。
- `?example=1` 仅用于演示设计稿交互，不查询、修改知识库，也不提交给 Agent。
- 计划保存在 `localStorage` 的 `pelican:plans:v1`，记录保存时的回答、条件与版本，不会重新计算、扣库存或写游戏存档。不同浏览器、端口和设备不会自动同步。
- 知识审核只记录用户决定，发布在独立页确认并由后端检查。前端不自动批准任何记录。
- 来源详情使用安全 HTTPS 链接。Markdown 不启用原始 HTML。用户在设置里填写的模型密钥保存在 `localStorage` 的 `pelican:chatecnu-key:v1`，刷新和重新打开后恢复，同一浏览器与地址的标签页共享，更换或清除会同步；只有发送对话时通过 Authorization 请求头交给本机后端，不随任务保存。清除密钥只删除这一项，不影响计划。

## 视觉与可访问性

沿用 `design/mockups-v1` 的奶油纸色、木色边框和叶绿色按钮。`styles.css` 顶部集中定义设计变量；800px 以下使用抽屉导航，560px 以下调整表单、卡片和操作区。图谱提供列表视图，图片框选提供键盘可用的百分比输入。抽屉使用 Radix 焦点管理，支持 Escape，保留焦点指示并尊重减少动态效果偏好。

## 使用的技能与官方文档

开发参考并安装了以下上游技能（不参与项目运行，也不需项目使用者安装）：

- [Vercel React Best Practices](https://github.com/vercel-labs/agent-skills/tree/main/skills/react-best-practices)：页面拆包、请求组织与存储版本。
- [Vercel Web Design Guidelines](https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines)：可访问性与响应式检查。
- [Anthropic Frontend Design](https://github.com/anthropics/skills/tree/main/skills/frontend-design)：保留项目主题和主要操作的视觉焦点。

组件 API 参考 [React Flow](https://reactflow.dev/learn)、[React Flow 13 迁移说明](https://reactflow.dev/learn/troubleshooting/migrate-to-v13) 和 [shadcn/ui Vite 安装文档](https://ui.shadcn.com/docs/installation/vite)。

## 验证边界

自动测试覆盖缺知识库提问、中文输入法、图谱关系方向、孤立节点、计划版本隔离与损坏存储恢复。Python 测试覆盖 SPA 子路径、静态资源边界与原有任务规则。实际问答和图像匹配还需要有效快照、原文、图片与模型额度；页面通过不代表缺失的知识数据已经恢复。
