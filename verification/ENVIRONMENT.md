# 星露谷项目本机核验环境

配置日期：2026 年 11 月 12 日，Asia/Shanghai。当前环境已可用于技术核验。Python 隔离环境、依赖一致性、Semantica 基础构图和跨进程来源读取检查通过；真实 Wiki 数据与游戏功能仍按 [PLAN.md](PLAN.md) 的 V01—V08 待执行。

## 1 实际配置

| 项目 | 本机结果 |
|---|---|
| 系统与架构 | macOS 27.0，arm64 |
| 项目解释器 | 项目根目录 `.venv/bin/python`，Python 3.12.14 |
| 基础解释器来源 | 已存在的 Codex 随附 Python 3.12.14；未修改该运行时 |
| 环境隔离 | `.venv`，不继承 system site packages |
| Semantica | PyPI 发布版 0.7.0 |
| 页面和网络工具 | BeautifulSoup 4.15.0、lxml 6.1.3、httpx 0.28.1 |
| 图片与配置 | Pillow 13.0.0、PyYAML 6.0.3 |
| 测试工具 | pytest 9.2.0 |
| 依赖锁定 | 51 个发行包全部固定版本和 SHA-256；实际安装与报告一致 |
| 环境磁盘占用 | 本次 `du -sh .venv` 为 578M，约 578 MiB |
| 本轮模型调用 | 0；未下载模型权重 |

系统默认 `python3` 仍是 3.9.6。运行项目时使用 `.venv/bin/python`，或激活环境后使用 `python`。当前终端 PATH 中没有 uv、Node；本轮 CLI 核验不需要它们。Codex 也提供随附 Node，但本次未把它加入 PATH、未安装前端包。尚未初始化 Git。

历史核验的基础解释器由 Codex 管理，虚拟环境仍依赖其基础运行时。若运行时被移动或清理，应使用可用的 CPython 3.12 重新建立虚拟环境。独立新机复现尚未执行；已有锁文件与操作步骤可供后续验证。

## 2 现在如何使用

进入工作区后，不需要先激活环境即可运行：

```sh
.venv/bin/python --version
.venv/bin/python verification/probes/environment_probe.py
```

如果要在当前终端持续使用项目解释器：

```sh
source .venv/bin/activate
python --version
```

退出该终端环境使用 `deactivate`。这只改变当前 shell 的 PATH，不修改系统 Python。

## 3 已执行的检查

最后一次环境检查时间为 2026 年 11 月 12 日 10:53:56—10:53:57，Asia/Shanghai。命令退出码为 0，四阶段共 87 条断言通过。

| 阶段 | 实际检查 | 结果 |
|---|---|---|
| pip-check | 包的依赖约束是否一致 | PASS，退出码 0 |
| inspect | 虚拟环境、解释器版本、模块来源、关键模块导入和接口签名 | PASS，退出码 0 |
| write | 人工 2 节点 1 条边调用 GraphBuilder，JSON 导出，显式 SQLite provenance 写后读 | PASS，退出码 0 |
| read | 写进程退出后，新进程重建图并重开来源库，校验稳定字段、关系查询与来源校验和 | PASS，退出码 0 |

写入采用 `GraphBuilder` 与显式 `ProvenanceManager(storage_path=...)`，图 JSON 和来源 SQLite 分别保存。没有依赖包装器自动记录真实来源的假设。三个检查进程未出现记录到的网络连接尝试，未加载 torch、spaCy、transformers、sentence-transformers 或 gensim。检查脚本会禁止 Python socket 联网并保留尝试记录。

这是 **ENVIRONMENT_SMOKE**：所有数据明确标注 `fixture=true` 和 `fixture:environment-smoke`。它证明当前包与基础接口可用，不代表已完成 Wiki 构图、规则审核、截图匹配或 V02 真实数据验收。计划状态仅将 V00 环境项标为 PASS；V01—V08 保持 NOT_RUN。

## 4 结果和安装记录

- 汇总：`verification/results/environment/summary.json`。
- 最终检查：`verification/results/environment/smoke/20261112T025356.240070Z-57770064/result.json`，同目录保存人工图、来源库、各进程结果。
- 脚本：`verification/probes/environment_probe.py`；重复运行会创建新的 run ID，保留以前的记录。
- 安装报告：`verification/results/environment/install-report.json`，含包来源与下载哈希。
- 实际版本：`verification/results/environment/installed-packages.json`、`installed.txt`。
- 日志：`verification/logs/environment/`。第一次沙箱内解析因 DNS/网络限制退出 1；获网络执行许可后的解析与安装均退出 0。首次 smoke 中的 pip 缓存不可写提醒已通过当前进程的 `PIP_NO_CACHE_DIR` 消除，原记录保留，未修改全局缓存权限。

依赖入口是 `requirements/verification.in`，实际复现使用 `requirements/verification.lock.txt`。后者包含本次取得的 macOS arm64、CPython 3.12 wheel 哈希，不能当作 Linux、Windows 或其他 Python 版本的通用锁文件。

## 5 同平台重建步骤

仅在新目录或确定需要重建环境时执行；不要覆盖仍在使用的 `.venv`。选择已有 CPython 3.12 解释器建立隔离环境，本机创建时使用了上文随附解释器：

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip --isolated install --require-hashes -r requirements/verification.lock.txt --disable-pip-version-check --no-cache-dir
.venv/bin/python verification/probes/environment_probe.py
```

本机 `python3.12` 没有加入全局 PATH，上述第一行是新环境的通用写法；在本机重建时可改用已记录的完整解释器路径。当前环境已经创建，无须重复安装。

依赖安装需要访问 PyPI。安装完成后，环境检查本身可以离线执行；本次未保存完整离线 wheel 仓库，不能宣称新机器无需网络就能安装。不同平台需要基于 `verification.in` 重新解析和验证兼容锁文件，不能删除哈希来勉强使用本锁。

## 6 下一步范围

下一阶段按 PLAN 的 V01 获取有限真实 Wiki 页面、图标与阶段图，再进行真实资料驱动的 Semantica 核验。模型接口、真实截图、游戏确切版本、来源审核和完整应用均未在本次环境配置中验证。前端、图数据库服务、原论文训练依赖及大型视觉模型暂未安装。
