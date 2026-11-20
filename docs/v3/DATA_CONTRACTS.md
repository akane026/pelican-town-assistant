# V3 数据契约

实现：`stardew_agent/core.py`、`parsing.py`、`visual.py`、`knowledge.py`。

Asset=原始文件哈希；Occurrence=来源修订＋DOM定位＋图片URL；Region=资产＋原图归一化xyxy＋方法版本；Observation=像素输入＋抽取器/请求键；Alignment=出现位置＋目标稳定ID＋观测版本。相同像素允许多个实体/状态，不以像素相同合并实体。

Relation 主键保留主语、谓词、宾语和条件；Fact 主键保留主体、属性、值、单位和条件，多值进入冲突记录。来源与审核单独保存。Semantica 中 Relation 被重化为节点，支持有向多谓词；实际查询恢复这些语义。

状态：candidate、validated_auto、approved_human、rejected、conflicted。正式发布权限独立于抽取分数；本轮无人代签。模型的自信分数不是概率。

快照覆盖全部语义图、图文关联和来源/资产；独立校验导出图、来源SQLite和索引哈希。任务绑定快照与 revision；EvidenceBundle 不包含图句柄，计算模块不能读任意图。

开发和增量 A/B 划分见 configs/corpus.json；单测合成 HTML 明确叫 Synthetic_Fixture，不计真实新页面。人工标注应从源页面抽样并保留漏项，不仅对已有对齐打分。原截图按源图分组，仅当历史诊断，不冒充新盲测。
