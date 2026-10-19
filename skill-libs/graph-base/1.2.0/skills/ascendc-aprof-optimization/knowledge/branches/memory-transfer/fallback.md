---
schema_version: aprof.knowledge-record/v1
id: implementation.memory-transfer.fallback
kind: recipe
version: 1.0.0
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
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: implementation.memory-transfer
references: []
evidence_status: source_reviewed_not_benchmarked
---

# 搬运与写回 回退方法

保留当前正确实现，逐项确认 C2 参数与 API 支持。不能满足前提时记录失败和缺项，调用相应辅助技能；不要绕过所有权、容量或精度边界。验证使用原 oracle 全 case，性能结果不能覆盖正确性失败。
