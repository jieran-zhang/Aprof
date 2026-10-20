---
name: tool-npu-compute
description: 在受支持的 Ascend 950 上采集和解释 npu-compute 算子报告，或分析已有 .npu-rep、Section CSV、summary.jsonl、HardwareInfo.jsonl 和 PipeTrace.json。
license: CANN-2.0
---

# AProf npu-compute 工具

已核实的上游支持范围为 Ascend 950 / dav-3510 Ascend C kernel，不包含 910C/A3；A3 使用 [ops-profiling](../ops-profiling/SKILL.md) 与 msprof。实际执行仍需确认硬件、CANN 和工具兼容性，不能仅靠工具支持列表；来源见 [兼容说明](NOTICE.md)。

采集读 [采集与身份](references/collection.md)：保留目标 argv/cwd，查询已安装 Set/Section 支持，检查退出码与实际报告/导入产物。沿用已有授权，不因缺工具升级系统 CANN/driver。

分析读 [证据语义](references/evidence.md)：保留原始文件与 collection 身份、缺失值，按假设选 Section，区分观测差异和可能原因。schema 通过或目标程序成功都不能单独证明有效采集或性能收益。

本技能只规定工具语义。独立机制采集、完整正确性、来源回放与正式交接见 [profiling 技能](../ascendc-aprof-profiling/SKILL.md)；不得替代统一计时或自行接纳候选。

Pipeline 可用本地只读检查器：

```bash
python3 scripts/inspect_pipe_trace.py <PipeTrace.json> --format json
```

检查器验证保留的上游 trace 格式；指标正式校验仍由 runtime 完成。使用事件数或忙碌时间前先读采样范围限制。
