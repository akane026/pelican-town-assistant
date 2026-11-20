# 复用映射

| 原文件 | V3 使用方式 |
|---|---|
| verification/common.py | 参考哈希、原子写入与离线审计；V3 新目录独立配置 |
| verification/graph.py | 复用已实测 Semantica 0.7.0 调用方式；新增适配器覆盖多模态类型、方向和完整快照 |
| verification/knowledge.py | 保留基线；替换按作物分支的解析为模板与清单驱动，不复制作物参数表 |
| verification/vision.py | 复用像素模板思想与预处理；候选改为来自新快照的 Asset/Region/Alignment |
| verification/calculators.py | 复用纯计算函数；不复用带整图句柄的 EvidenceResolver |
| verification/chatecnu.py | 复用已验证请求、脱敏、超时与工具协议；新运行日志、预算台账独立 |
| verification/pipeline.py | 保留诊断基线；以动态单 Agent 工具循环替代业务路由 |
| verification/data | 只读导入已有合法取得资料；新数据在 data/，原结果不变 |

V3 包放在 `stardew_agent/`，支持直接 `python -m stardew_agent.cli`；没有同能力的第二套生产真值图。原验证目录只作为历史证据与纯函数依赖。
