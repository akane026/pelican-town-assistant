# V3 实际起点

基线冻结于 `artifacts/v3/20261112T073158Z/baseline/`。归档为只读 `original.tar.gz`；manifest 逐文件保存原代码、资料、结果的 SHA-256。原文件复跑前后完全一致。

实际命令：`.venv/bin/python scripts/freeze_baseline.py`。冻结脚本退出 0；隔离副本内真实命令 `.venv/bin/python -m verification.run_all --offline` **退出 2 / PARTIAL**，耗时约 15.08 秒。原测试语义未改变；在线调用没有重跑。stdout、stderr、逐阶段输出均保留在隔离副本。

原工作区无前端、无生产 Agent、无 Git 仓库；检查上级也不属于仓库。已执行本地 `git init`，没有配置或推送远端。G0／ITER1 从未被当作已执行。

已确认缺口：解析有作物分支；Semantica 主要构图和溯源；检索三粒度不完整；计算隐式查询整图；Agent 是固定两分支；原检索计时和边访问统计不完整；snapshot_id 未覆盖全部图结构；精确版本、独立审核、图像效果及正式题集未完成。

原结果是诊断基线，不重新命名为 V3 验收。所有新增结果写入 `artifacts/v3/`，不得覆盖 `verification/results/`。
