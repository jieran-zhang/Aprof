---
name: ascendc-performance-best-practices
description: 在冻结并行计划内，结合证据选择 Ascend C 搬运、流水、缓冲区、Vector 或 Cube 优化。
---

# AProf 执行优化实践

搬运、流水、Vector、Scalar 和缓冲区问题见 [执行机制](../ascendc-perf-optimize/references/execution-mechanisms.md)；涉及任务分解时看 [算法族](../ascendc-tiling-design/references/algorithm-families.md)。用 `npu-arch` 核验能力，通过 `ascendc-aprof-optimization` 提出候选。

高利用率不等于瓶颈，小 workload 的空闲核也不等于实现低效。结合实际工作量、字节数和依赖链比较 workload 可达边界。全局算法修改归并行规划；执行调优保持计划 hash 不变。
