---
name: ops-profiling
description: 将 AProf 机制采集路由到受支持的 950 npu-compute 或 910C/A3 msprof，保留可供 runtime 回放的原始报告。
---

# AProf 硬件机制采集

同源构建与完整正确性通过后，按 [profiling 技能](../ascendc-aprof-profiling/SKILL.md) 选择后端。兼容的 950/dav-3510 优先 npu-compute；当前 910C/A3 用 `msprof op`，其余架构需实际能力检查。保持系统 CANN/driver 不变。

按 [采集接口](../ascendc-aprof-profiling/references/collector-interface.md) 记录独立机制采集与标准化来源。npu-compute 文件语义见 [工具技能](../tool-npu-compute/SKILL.md)。PMU 只按路由或机制需求采集，不代替完整调用计时。

下列 msprof 工具用于补充视图或读取历史报告。路径相对安装技能目录；全部输出（包括 `<archive-dir>`）放入任务临时空间，永久归档属于可选的任务后采集。

```bash
bash scripts/msprof_profile_run.sh --help
bash scripts/msprof_profile_run.sh --warm-up=10 --output=<unique-dir> -- <binary> <args>
python3 scripts/msprof_perf_summary.py <PROF_GROUP-dir> <archive-dir>
python3 scripts/perf_summary.py <OPPROF-dir> <archive-dir>
```

`--compare`/`--batch` 是兼容工具，不承担当前候选性能接纳。当前唯一计时方式见 [统一计时协议](../ascendc-aprof-profiling/references/unified-timing.md)，正式工程判定与报告出口见 [主工作流](../ascendc-aprof-coordinator/SKILL.md)。旧 v5 配对样本仅按其历史协议回放。

保留原始 CSV/JSONL/trace、准确命令、source/binary/workload hash、collection/kernel 身份、硬件和 dispatch key。缺失字段保持未知；人工摘要不是候选判定或训练奖励。
