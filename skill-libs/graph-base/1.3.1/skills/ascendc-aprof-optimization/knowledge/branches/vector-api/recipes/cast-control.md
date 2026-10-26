---
schema_version: aprof.knowledge-record/v1
id: implementation.vector-api.cast-control
kind: recipe
version: 1.1.0
status: deprecated
title: Cast 合并与标量控制简化（兼容摘要）
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/common/scalar/coding_principles.md
  original_path: ops/ascendc-performance-best-practices/references/common/scalar/coding_principles.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 478
  sha256: sha256:a387544bac3f38ad940fae2930e75c9f7cda45c8e25324f4cd864bee1ce4827c
  excerpt_sha256: sha256:a387544bac3f38ad940fae2930e75c9f7cda45c8e25324f4cd864bee1ce4827c
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/type_conversion/Cast.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/type_conversion/Cast.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 643
  sha256: sha256:a41d8e8b10d541452de9c4542158d0bba6bc53f15e68c3d1d929712856a11f12
  excerpt_sha256: sha256:a41d8e8b10d541452de9c4542158d0bba6bc53f15e68c3d1d929712856a11f12
learning: {}
tags: []
seed_reason: 审读五个固定开源修订中的直接来源，以中文提炼实现契约；保留旧 ID 含义，不承诺目标 SDK 编译结果或 NPU 性能收益。
parent: implementation.vector-api
references:
- implementation.scalar-control.constant_lifetime
- implementation.scalar-control.hot_loop_address
- implementation.scalar-control.tilingdata_access
- implementation.vector-api.cast
evidence_status: source_reviewed_not_benchmarked
---

# Cast 合并与标量控制简化（兼容入口）

本条保留 `implementation.vector-api.cast-control` 的既有 ID、路径与原含义：检查冗余 Cast、索引/分支重复和标量热路径；只消除不改变可见舍入的转换，外提循环不变量并缩短对象存活期。原先 Cast 与 Scalar 两类机制混在同一条中，现标记为 deprecated 兼容摘要，历史 C3 记录仍可解析；它不再承担独立优先候选，也不能把旧 ID 改作无关新配方。

实际实施分别读取完整方法：

- `implementation.vector-api.cast`：转换链、dtype 对、舍入模式、mask/count/stride、别名和 UB 生命周期。
- `implementation.scalar-control.hot_loop_address`：地址不变量外提、首主尾分离、显式循环，保持同一访问序列。
- `implementation.scalar-control.tilingdata_access`：只读 GM 字段和热点局部缓存，保持 TilingData ABI。
- `implementation.scalar-control.constant_lifetime`：constexpr/有限模板、对象别名、存活期及仅固定布局允许的静态 tensor。

兼容候选仍须先取得 C2 action、模板快照、所有权、允许自由度、dtype 与精度标准。`float→half→float` 保留一次可见舍入，不能当纯格式搬运删去；“Scalar 高”也不授权删除 queue/event。首尾分离必须覆盖空循环、单块同时首尾和尾部有效长度。spill 是否下降以汇编/编译报告为准，不根据源代码变量数推断。

来源事实：固定 scalar 文档支持局部变量、循环分离、常量传播与生命周期改写；固定 Cast 文档明确 dtype/舍入与混合宽度 stride。拆分是知识组织与工程提炼，不修改算法。构建前代码审查，完整 oracle case 与极值/NaN/Inf/有符号零验证通过后再比较 Task 时间；失败保留实际改动和日志，回退 C2 正确路径或请求重规划，不换精度标准继续计时。

平台条件分别由新条目约束；910C/A3 不使用 3510 专属 VF/RegBase/SIMT。此兼容摘要没有独立硬件收益数据。
