# 固定上游建图审计

固定提交 `e9cc3f5728bb8cf1d3904614532a7345db0f0f47`；完整取得的参考文件和 SHA-256 见 `UPSTREAM_MANIFEST.json`，原文件在忽略提交的 `third_party/mkg-rag-e9cc3f5/`，保留 Apache-2.0 LICENSE。

入口 `rag/mmkg.py` → `MMRAG` → `extract_entities`：先抽文本实体关系，再读取每图描述/scene graph，调用 mapping，最后把视觉属性放入节点和边并构建索引。

| 环节 | 实际落点 | 分类 |
|---|---|---|
| 原实体/关系/mapping 记录解析 | upstream.py 按原函数 AST 隔离导入，不触发默认模型 | 原组件运行；测试结果见 artifacts/v3/upstream |
| 原 scene graph 格式化、ROI 裁剪 | 原函数处理本项目真实视觉观测和真实 PNG | 原组件运行 |
| 原图片属性融合 | 原 `_handle_images_attribute`，真实观测＋适配 mapping 输入 | 原组件运行，非原模型预测 |
| 文本模型调用 | model.py 复用 ChatECNU；construction.enrich_text | 接口替换及结构化格式适配 |
| Wiki 分段/模板 | parsing.py | 领域重实现 |
| 视觉观测/区域 | visual.py：像素统计、真实 MLLM，明确不同方法 | 领域重实现 |
| 对齐/有向多谓词融合 | visual.align_graph、construction.merge_graphs | 领域重实现 |
| 正式图与来源 | knowledge.py 的 Semantica 0.7.0 | 存储适配，单一真值 |

原 `build.py:806` 排序端点，`_handle_images_attribute` 接受逆向端点作为匹配，并在未用整图时附加整图到高连接度节点。生产适配不用这些启发式建立游戏机制关系。生产 Relation ID 包含主语、谓词、宾语、条件，视觉说明引用 Relation ID。

原缓存包装器 `build.py:642` 的显式缓存哈希主要依赖文字。生产缓存包含图片字节哈希、上下文、模型、提示版本及 schema；不同图片不共用视觉响应。

完整原始建图入口、EGTR、QM 均未运行；默认大模型、faiss-gpu 和自定义 QM 注册/权重不能作为建图前提。QM 代码存在，但未核实到完整专用实现/权重及接线，保留为 BLOCKED，不称论文完整复现。
