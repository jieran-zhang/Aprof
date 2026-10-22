---
schema_version: aprof.knowledge-record/v1
id: implementation.memory-transfer
kind: router
version: 1.0.0
status: active
title: 搬运与写回 路由
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
parent: implementation.root
references: []
evidence_status: source_reviewed_not_benchmarked
routes:
- target: implementation.memory-transfer.coalesce
  match: []
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.memory-transfer.coalesce
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.plan_freedom
  - constraint.output_ownership
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: implementation.memory-transfer.example.tile-amortization
  match:
  - field: examples
    op: contains
    value: tile-amortization
  exclude: []
  required_evidence: []
  prior_score: 1
  fallback: false
  seed_reason: 探索性参照，需要额外证据。
- target: implementation.memory-transfer.fallback
  match: []
  exclude: []
  required_evidence: []
  prior_score: 0
  fallback: true
  seed_reason: 未知类型保留语义正确的现有方案并补证据。
---

# 搬运与写回 路由

根据 C2 冻结的方案和待实现变换，选择以下方法。保持算法、所有权和数值语义；越过 C2 自由度时返回重规划。

- [连续搬运合并与批量写回](recipes/coalesce.md)

- 按需回查 [tile-amortization](examples/tile-amortization.md) 的原协议和失败记录。
