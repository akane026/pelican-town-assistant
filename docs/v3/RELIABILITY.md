# 可靠性与独立复现记录

新建并按哈希锁独立安装的 `.venv-repro`：完整工程测试 **70 passed**，命令真实退出 0。

原始日志：`artifacts/v3/execution/20261112T103314.487417Z-19-final-independent-suite/stdout.log`；代码指纹：`artifacts/v3/execution/20261112T103314.487417Z-19-final-independent-suite/code_manifest.json`。

上述是模块 / API 工程断言，不是正式业务正确率。模型故障使用显式合成夹具；真实模型执行另有日志。

独立环境实际从 `.venv-repro/lib/python3.12/site-packages` 加载 Semantica，重新读取 1,150 条来源记录并计算甘蓝 12 个普通品质销售 1320g。没有复制虚拟环境。共享的是本机已合法取得的冻结来源，没有冒充重新抓站或重新请求视觉模型。

## 已执行覆盖

- Real Semantica provenance roundtrip and directed multi-predicate graph
- Unreviewed formal mode rejection, isolated release subset, failed export rollback, review tampering and candidate immutability
- HMAC bundle tampering, task/snapshot mismatch, changed source files, deleted relationship/unique source
- Relevant vs irrelevant fact intervention and redundant valid source
- Duplicate import, changed page revision, raw/asset byte drift, partial failure resume and cache reuse
- Model timeout/HTTP429/malformed JSON via explicit synthetic fixtures
- Loopback Host/Origin/CSRF controls, corrupt image/path rejection and outside registered ROI denial
- Shared BQ/D image reranking contract, invalid IDs/duplicates fallback, no-model degradation
- Task correction, mid-loop revision invalidation, inventory copy constraints and no-evidence answer rejection
- Deterministic calculation answer projection; bounded model-assisted checking for non-calculation answers

## 尚未证明

- No independent human knowledge/rule approvals or complete formal 60-question run
- No new held-out screenshot recognition score or full source-unit alignment gold
- A real semantic-check pilot missed an ambiguous old sentence. Calculation answers now project validated outputs, but general factual natural-language checking is not a proof of truth
- No load/stress guarantee, cross-machine acquisition reproduction, original QM training or full EGTR execution

Publication success tests use temporary copies and explicitly synthetic local_user fixtures. Production current.json remains absent.
