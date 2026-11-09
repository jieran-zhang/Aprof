---
name: ascendc-perf-optimize
description: 依据工作负载证据和已发布 SkillGraph 路由，区分 AProf 算法并行规划与执行调优。
---

# AProf 优化边界

验证或复用冻结的任务分解、所有权、算法、归约和 workspace 计划。缺少计划或计划发生变化时进入 `ascendc-aprof-parallel-planning`；其余由 `ascendc-aprof-optimization` 在选定计划与 workload group 内实现一项执行修改，并把分发实现 hash 重新绑定到候选。

区分独立任务不足和已有任务执行低效。修改分区轴、split-K、合并树或跨核所有权需新并行计划；所有权不变时的 tile 长度、搬运粒度、缓冲深度、调度或等价局部 API 属于执行调优。

单核瓶颈见 [执行机制](references/execution-mechanisms.md)，分解选择见 [算法族](../ascendc-tiling-design/references/algorithm-families.md)。这些资料不提供性能证据；使用实际目标的源码、计数器与 统一计时协议（同名参考，非历史原件：[unified-timing.md](../../../../../skills/ascendc-aprof-profiling/references/unified-timing.md)）。跨轮保留通过正确性与运行检查的父版本、源码谱系及失败尝试。性能接纳单独记录；探索父版本不是 production best。

> 文档适配说明：本页已修复引用；缺失材料的链接已移除，同名补充参考不代表历史原件。来源及历史回放使用[保留的证据原文](../../../../../sources/document-originals/3a1fc137d012c04475886c0434929678dca569a27b4df67e4b9e0b0b7359a2bf.txt)。
