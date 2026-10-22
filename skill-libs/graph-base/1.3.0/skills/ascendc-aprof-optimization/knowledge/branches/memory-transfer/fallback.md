---
schema_version: aprof.knowledge-record/v1
id: implementation.memory-transfer.fallback
kind: recipe
version: 1.1.0
status: active
title: 搬运与写回 回退方法
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
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/data_move/DataCopyPad_GMToUB.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/data_move/DataCopyPad_GMToUB.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 3
  - 320
  sha256: sha256:8fd9166a39e7ab163695f1d965ad633725afa1c60cff08708b439f58f2a646ee
  excerpt_sha256: sha256:643aefa2bdb90c4fa26a228d9f36b5d487f11b9ebbcc80c4d7d3f52273abf98c
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/data_move/DataCopyPad_UBToGM.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/data_move/DataCopyPad_UBToGM.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 58
  - 148
  sha256: sha256:23e9b37e62ff5c2fed4b142ad65b346f8987aa6be527e291dae63466dc88f315
  excerpt_sha256: sha256:e4fc628736c5c7870254ce95b9ef24afb65e80df4762615190a2b173e22cb01d
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/04_memory_access/data_copy/data_copy_ub.h
  original_path: examples/01_simd_cpp_api/05_best_practices/04_memory_access/data_copy/data_copy_ub.h
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 21
  - 145
  sha256: sha256:f5ca47ce371eb60e16d3fac8bb0a5f8921c62de8515d22de92b900e3c7733911
  excerpt_sha256: sha256:848f0dfa47facbfcddf126f931b9a62f125a0aced77b4f9229eb7eb23768b8f0
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/data_structures/GlobalTensor/SetL2CacheHint.md
  original_path: docs/zh/api/SIMD-API/basic_api/data_structures/GlobalTensor/SetL2CacheHint.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 3
  - 112
  sha256: sha256:62807570650c1a69ab2bf0ba2bce606a4a3141d5d9d976fdbf3bdaf1d4df1092
  excerpt_sha256: sha256:8b3a062e7527c371f256ed15a82ae19d75e97d7d618d7381aa07605d627ce6ee
learning: {}
tags:
- bounds
- copy-fallback
- ownership
seed_reason: 审读固定开源修订并提炼中文实现配方，保留既有 ID 语义；API 单位以实际 API 文档为准；未做目标 SDK 编译或 NPU 性能验证。
parent: implementation.memory-transfer
references:
- implementation.memory-transfer.coalesce
- implementation.memory-transfer.strided-pad
- implementation.tiling-tail.valid-length
evidence_status: source_reviewed_not_benchmarked
---

# 搬运与写回的保守落地路径

## 何时使用

原实现正确，但连续区间、stride 单位、DMA 支持、GM 别名或输出所有权任一项尚不能证明时，保留原搬运轨迹，先消除非法参数。fallback 是明确的正确实现候选，不是跳过尾块、只运行整齐 case 或把错误吞成零输出。输入仍是 C2 冻结的任务、dtype/layout、有效范围和可调参数；需要改变所有权或算法的方案返回重规划。

## 从地址到容量逐项核验

为每个 copy 建表：方向、具体重载、首元素偏移、有效元素、有效字节、物理行 pitch、UB 对齐跨度、所属任务和生产/消费完成点。设元素字节 `s`，长度 `v`，只允许读取 `[base,base+v)` 的合法 GM 元素；`v*s` 先在宽整数中计算。字段窄化前核对 API 范围。UB 行大小使用 `AlignUp(v*s,32)`，不能据此扩展 GM 有效区间。

| 未满足的前提 | 保守实现 | 仍必须满足 |
|---|---|---|
| 相邻区间不连续或属于不同输出任务 | 保留逐段 copy | 每段长度、所有权及顺序正确 |
| 规则 stride 字段超限 | 拆成更多行组，或保留已验证逐行路径 | 每组首地址重算，不能截断 stride |
| 尾部非32B对齐 | 使用目标支持的 DataCopyPad 重载及有效 `blockLen` | UB 32B首址与行padding容量合法 |
| DataCopyPad 目标不支持/SDK证据缺失 | 保留已有正确尾部实现 | 没有已有合法路径则报告能力缺项 |
| L2 复用不清楚 | 保留默认/既有 NORMAL | 不把 hint 当作同步或驻留保证 |
| in-place 写可能破坏未来输入 | 保留原读写调度或原暂存 | 先读范围与最终写范围有明确顺序 |

## 单段尾部的最小契约

`xGm` 为完整输入 `GlobalTensor<T>`，`xLocal` 为该重载允许的位置和类型、32B对齐的 UB；`offset/valid` 是 C2 本任务有效范围内的元素数。若目标为 Atlas A2/A3 且已核验无 mode 的 GM→UB 重载，构造 `DataCopyExtParams{1, valid*sizeof(T), 0, 0, 0}`，配无显式 padding 的 `DataCopyPadExtParams<T>{false,0,0,0}`；容量至少 `AlignUp(valid*sizeof(T),32)`。先判 `valid>0` 再发起本段和配套同步，计算只使用 valid 元素。dummy 未初始化为数学中性值，不能让其进入归约。

UB→GM 非对齐写回只写 `valid*sizeof(T)` 有效字节；重载没有 GM→UB 的 pad 参数，且 UB 端 `srcStride` 的单位为32B block。尾写需要与相邻 task 的物理写粒度约束一起审查，不能仅凭逻辑地址不重叠就宣称所有短写组合合法。

`peakUB` 必须包含所有 queue 槽、输入/输出、转换和 workspace；多块 copy 的每行对齐分别计算。DMA 读 UB 未完成前输出槽仍存活，DMA 写 UB 未完成前输入不能计算，所有消费者结束前不能覆盖。任何回退都不得为了少付事件成本而删去完成边。

## 验证与退出条件

至少覆盖0任务既有语义、一个元素、对齐边界±1、完整tile、跨tile、最后一个核、非连续 pitch和别名相关case，沿用原oracle全域。确认有效字节总量、最后地址、每个输出的唯一写者与静态 UB 分配均可解释。正确性通过才比较同协议 Task 与 MTE 时间；保留失败日志、原版和候选的参数与源码身份。若问题来自目标API不支持、所有权改变或容量只能靠算法改写解决，明确列缺项并回到C2。

来源事实：DataCopyPad 的单位、对齐、dummy及产品约束来自 asc-devkit API 文档；data_copy 样例展示规则行与尾列。表中回退层级和地址核验顺序是工程提炼。本条不给来源性能数字、对齐经验或 tile 常量以跨平台资格。
