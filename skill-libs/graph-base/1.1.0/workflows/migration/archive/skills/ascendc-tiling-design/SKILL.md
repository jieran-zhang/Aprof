---
name: ascendc-tiling-design
description: 在 AProf 并行计划确定后，设计满足容量限制的 workload 分发与核内 tiling，包括直调 tiling key 接线。
---

# AProf Tiling 与分发

读取 [tiling 与分发](references/tiling-dispatch.md)。Host 元数据选择算法、workload group 和 uint64 tiling key，该 key 必须选中真实 kernel 实现。保留容量查询、动态 shape 和通用回退。

改变任务分解、归约或所有权前使用 `ascendc-aprof-parallel-planning`。选定计划内，根据全部存活张量、队列深度、对齐、临时区和 workspace slot 推导 UB/L1/L0 占用；使用运行时 AIC/AIV 数和可用内存，不能用产品名常量替代。

MatMul、Norm/Reduction、Sort/TopK 和 attention 见 [算法族](references/algorithm-families.md)。精度阈值和语义来自算子声明的 reference/checker，无需外部精度标准技能。
