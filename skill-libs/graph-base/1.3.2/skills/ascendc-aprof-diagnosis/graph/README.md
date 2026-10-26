# 机制模板知识图

当前版本v0006由55个观察模板、28个机制模板、28个变换模板及条件关系构成；具体计数和审查见迁移台账与生成目录。历史v0003保持冻结，不直接视为已验证机制。

从[诊断skill](../SKILL.md)进入，运行`diagnosis retrieve`取得完整Problem轻目录和Symptom邻接，再按需读必要Problem正文。没有旧边不排除候选，不固定top-k，不要求沿SPA路径执行。

模板字段与来源规则见[FORMAT](FORMAT.md)，关系阅读索引见[GRAPH](GRAPH.md)，旧先验说明见[INITIALIZATION](../../../workflows/references/development-records.md#skills-1-3-2)。任务推理、案例与知识提案分别保存，机制与交接基础规则见[v0004 说明](../../../workflows/references/diagnosis-v4.md)；当前 Action 条件分类、试验选择与 R2 反馈按[v0006 选择与复盘规则](../../../workflows/references/action-selection.md)。

195 条 v0003 原始源码、REGION 身份和种子清单已迁入 scaffolding，位置见[开发材料索引](../../../workflows/references/development-records.md#skills-1-3-2)，继续用于旧编译兼容回归；`versions/v0003`与旧v0001/v0002保留原字节。当前源使用新schema，旧编译命令不能直接重编。
