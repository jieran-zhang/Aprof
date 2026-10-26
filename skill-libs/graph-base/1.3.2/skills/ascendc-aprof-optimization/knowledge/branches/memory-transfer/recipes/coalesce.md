---
schema_version: aprof.knowledge-record/v1
id: implementation.memory-transfer.coalesce
kind: recipe
version: 1.1.0
status: active
title: 连续搬运合并与批量写回
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/ops/ascendc-performance-best-practices/reference/common/datacopy_optimization_design.md
  original_path: ops/ascendc-performance-best-practices/reference/common/datacopy_optimization_design.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 351
  sha256: sha256:e8cc9f2915a016c276cf431de51a66748779c510f82de2cc293e523beaed679e
  excerpt_sha256: sha256:e8cc9f2915a016c276cf431de51a66748779c510f82de2cc293e523beaed679e
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/04_memory_access/data_copy/data_copy_ub.h
  original_path: examples/01_simd_cpp_api/05_best_practices/04_memory_access/data_copy/data_copy_ub.h
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 21
  - 145
  sha256: sha256:f5ca47ce371eb60e16d3fac8bb0a5f8921c62de8515d22de92b900e3c7733911
  excerpt_sha256: sha256:848f0dfa47facbfcddf126f931b9a62f125a0aced77b4f9229eb7eb23768b8f0
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/04_memory_access/data_copy/README.md
  original_path: examples/01_simd_cpp_api/05_best_practices/04_memory_access/data_copy/README.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 82
  - 394
  sha256: sha256:7126d511236c3539b2710934c468c56500e39ac336531597a3360d6c74282cff
  excerpt_sha256: sha256:9f27996a1bd449d385a01b00b0a11a0562c3e17bf8762c3e55e33dd241596031
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/00_vector_compute/add_high_performance/add.asc
  original_path: examples/01_simd_cpp_api/05_best_practices/00_vector_compute/add_high_performance/add.asc
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 27
  - 345
  sha256: sha256:f7d075958365a8fc1af9879e90ab6494573f8869d3a538832c537d8e0f905042
  excerpt_sha256: sha256:d2b85d269202c81ba81366f010df36bf3c512f17f84bd0b145c0dd1425e49cda
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/common/arch22/datacopy_optimization_design.md
  original_path: ops/ascendc-performance-best-practices/references/common/arch22/datacopy_optimization_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 55
  sha256: sha256:dbb672d9f6f872d02ba5a255ac9b1949595d8fa869efb174c27895da04560a38
  excerpt_sha256: sha256:10621504e99f08b702f2b096bf353ab282bc4da997e2d7e8b96df1a9f60c4c45
learning: {}
tags:
- batch-writeback
- byte-accounting
- contiguous-copy
seed_reason: 审读固定开源修订并提炼中文实现配方，保留既有 ID 语义；API 单位以实际 API 文档为准；未做目标 SDK 编译或 NPU 性能验证。
parent: implementation.memory-transfer
references:
- implementation.buffer-lifetime.reuse
- implementation.memory-transfer.strided-pad
- implementation.tiling-tail.valid-length
evidence_status: source_reviewed_not_benchmarked
---

# 连续搬运合并与批量写回

## 原理与适用条件

一次 DMA 的固定发射、循环控制和同步成本会被小块搬运反复支付。合并相邻且同属一个任务的有效区间，或用一个多块参数描述规则行段，可在不增加数学工作量的前提下减少发射次数。输入是 C2 已选 action、任务所有权、tile 范围、输入输出 stride、别名约束和 API 证据；只在其允许的参数范围内实现。行间有空洞时使用 `implementation.memory-transfer.strided-pad`，不能把空洞当作有效连续元素。

先列出每个输入/输出的 `(起始元素偏移, 有效元素数, 物理行跨度)`。只有前一段的末端等于后一段的起点、dtype/布局相同、且同一核拥有完整输出区间时，才直接合并；不同 batch、跨行 padding、广播输入和其他核的输出都构成边界。合并写回还要求全部结果在写回之前已生成且不会被覆写。

## 落地步骤与成本

1. 对固定 shape、相同地址集合比较原版与合并版；每个 tile 必须保留完整有效范围，不能通过漏搬尾段减少次数。
2. 读入若本来就是连续区间，优先延长一次搬运；规则矩形可增加 `blockCount`，同步重算 UB 的行间对齐。禁止用补齐的 GM 长度代替实际有效长度。
3. 多个短输出可积累到 UB 中连续槽，再统一写回；每个槽保留 producer→最后写回完成的存活期。结果需要立即被下阶段消费、存在 atomic/部分和语义或输出存在跨任务别名时，保留原写回顺序。
4. 合并后确认 MTE2/MTE3 与计算的完成边不变；队列 `EnQue/DeQue` 或现有显式事件必须覆盖更大的区间。只改变调用数量不足以证明流水合法。

记总有效元素 `N`、每元素字节 `s`、单次 tile 元素 `T`、每 tile 搬运次数 `c`，调用量约为 `c×ceil(N/T)`，有效流量应仍为 `N×s`（每个输入/输出分别计）。读写不同的两个 half 输入并产生一个 half 输出时，最小逻辑 GM 流量是 `6N` 字节；MTE2 和 MTE3 可重叠，不能把某一引擎时间当作三路总带宽的纯读时间。估算 `t≈calls×launchCost + bytes/effectiveBandwidth` 仅用于解释候选，最终比较同协议 Task 时间。

批量输出额外占用 `AlignUp(k×resultBytes,32)` 字节；完整 UB 预算还包括输入槽、转换、临时区、API workspace、queue 槽数和 padding。若这使输入 tile 变小、失去双缓冲或引入 spill，减少的写回次数可能得不偿失。

## 有上下文的搬运片段

下例只描述连续 float 区间；`xGm`、`yGm` 是长度至少 `offset+count` 的 `GlobalTensor<float>`，`xLocal/yLocal` 是不重叠、32B 对齐且各有 `count` 元素的有效 UB 视图。`offset/count` 均为元素数，Host 已证明 `count>0`、`count*sizeof(float)` 为 32B 倍数、字段/计数范围合法、输出只归本任务。沿用工程已核验的 producer/consumer 事件，不能从片段省略同步得到“无同步实现”。

```cpp
// CopyIn 阶段；将原先 k 个相邻小区间合为一个合法连续 count。
AscendC::DataCopy(xLocal, xGm[offset], count); // count 单位：float 元素
// 等现有 MTE2 -> Vector 完成边后，执行 C2 冻结的计算，生成 yLocal。
// 等现有 Vector -> MTE3 完成边后：
AscendC::DataCopy(yGm[offset], yLocal, count); // 同样只写有效元素
// MTE3 尚未完成读取 yLocal 时，仍不能复用其 UB 存储。
```

非对齐段使用核验过的 DataCopyPad 重载，以有效字节指定 `blockLen`；若合并后跨过不能读取的空洞，应拆成矩形多块或保留逐段搬运，而不是读取分配范围外的补齐数据。

## 失败边界、验证与来源

覆盖短于 tile、整 tile、tile±1、奇数行宽、不同物理 stride、alias 允许/禁止和最后一个核。检查总读写有效字节、最后有效地址、每个输出只写一次、峰值 UB 和流水完成边。性能观察调用次数、MTE2/MTE3 时间与 Task 时间；MTE 指令减少而总流量增长、核尾覆盖其他核、UB 槽提前覆写均应撤回该候选。构建前完成代码审查；精度错保留 oracle/完整日志，不以跑通的子集替代原 case 域。

来源事实：asc-devkit `data_copy` 用不同矩形 tile 展示发射粒度与 UB 占用的权衡；Add 样例展示双缓冲下的读写生命周期。这里的连续区间合并判据、流量等式与输出累积预算是工程提炼。样例的 tile、核数和实测收益仅限原配置，不构成 910C 的默认参数；本条没有目标硬件性能验证。
