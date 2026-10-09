# 采集侧 contract

这里维护研究记录的格式；通用执行、规划、gate、episode contract 由选定
skill release 的 `schemas/` 和 runtime 提供。调用方必须先绑定版本，不能从
catalog 的默认指针隐式切换。

| 范围 | 定义和权威校验 |
| --- | --- |
| memory / lesson v2 | 本目录的 JSON Schema；[trace_v2_dataset.py](../scripts/trace_v2_dataset.py) 校验引用、条件、来源和跨记录约束 |
| shared context | 本目录三个 `shared-context-*.schema.json`；[shared_context_report.py](../scripts/shared_context_report.py) |
| campaign 状态与预算 | [msprof_exploration_campaign.py](../scripts/msprof_exploration_campaign.py) 和 [trace_v2_campaign.py](../scripts/trace_v2_campaign.py) 中的现有版本化状态机 |
| Level2 测量与最终报告 | [测量协议](../workflows/level2_msprof_protocol_v2.md)、[搜索测量边界](../workflows/search-measurement.md)，以及执行器的身份和报告校验 |

重构保留原 schema 字节与协议语义。没有另外生成一套 campaign 或测量
schema；这些协议仍由现有状态机和证据校验代码执行。
通过 shape 校验不等于正式准入，也不自动获得训练资格。
