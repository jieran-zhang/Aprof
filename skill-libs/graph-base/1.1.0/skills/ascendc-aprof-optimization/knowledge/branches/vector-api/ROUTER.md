---
schema_version: aprof.knowledge-record/v1
id: implementation.vector-api
kind: router
version: 1.0.0
status: active
title: Vector / API 路由
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/ops/ascendc-performance-best-practices/reference/elementwise/vector_efficiency_design.md
  original_path: ops/ascendc-performance-best-practices/reference/elementwise/vector_efficiency_design.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 203
  sha256: sha256:9f427095336cbb2e8024b29f664648b75abfe3b499471b999b30867d5c29213a
  excerpt_sha256: sha256:9f427095336cbb2e8024b29f664648b75abfe3b499471b999b30867d5c29213a
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: implementation.root
references: []
evidence_status: source_reviewed_not_benchmarked
routes:
- target: implementation.vector-api.batch
  match: []
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.vector-api.batch
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.plan_freedom
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: implementation.vector-api.cast-control
  match: []
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.vector-api.cast-control
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.plan_freedom
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: implementation.vector-api.fallback
  match: []
  exclude: []
  required_evidence: []
  prior_score: 0
  fallback: true
  seed_reason: 未知类型保留语义正确的现有方案并补证据。
---

# Vector / API 路由

根据 C2 冻结的方案和待实现变换，选择以下方法。保持算法、所有权和数值语义；越过 C2 自由度时返回重规划。

- [Repeat / mask / stride 与批量 Vector API](recipes/batch.md)
- [Cast 合并与标量控制简化](recipes/cast-control.md)
