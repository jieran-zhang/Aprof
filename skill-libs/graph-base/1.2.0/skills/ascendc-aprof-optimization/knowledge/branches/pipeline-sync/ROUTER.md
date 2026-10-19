---
schema_version: aprof.knowledge-record/v1
id: implementation.pipeline-sync
kind: router
version: 1.0.0
status: active
title: 流水与同步 路由
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/ops/ascendc-performance-best-practices/reference/elementwise/double_buffer_design.md
  original_path: ops/ascendc-performance-best-practices/reference/elementwise/double_buffer_design.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 288
  sha256: sha256:142cc0055136ff3bc203672f4c4365cf4f09b41a175a7bfa1d89f3df3b2500ae
  excerpt_sha256: sha256:142cc0055136ff3bc203672f4c4365cf4f09b41a175a7bfa1d89f3df3b2500ae
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: implementation.root
references: []
evidence_status: source_reviewed_not_benchmarked
routes:
- target: implementation.pipeline-sync.pipeline
  match: []
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.pipeline-sync.pipeline
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.plan_freedom
  - constraint.dependency_lifetime
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: implementation.pipeline-sync.slots
  match: []
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.pipeline-sync.slots
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.plan_freedom
  - constraint.workspace_ownership
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: implementation.pipeline-sync.example.sigmoid-pipeline
  match:
  - field: examples
    op: contains
    value: sigmoid-pipeline
  exclude: []
  required_evidence: []
  prior_score: 1
  fallback: false
  seed_reason: 探索性参照，需要额外证据。
- target: implementation.pipeline-sync.example.prefetch-boundaries
  match:
  - field: examples
    op: contains
    value: prefetch-boundaries
  exclude: []
  required_evidence: []
  prior_score: 1
  fallback: false
  seed_reason: 探索性参照，需要额外证据。
- target: implementation.pipeline-sync.fallback
  match: []
  exclude: []
  required_evidence: []
  prior_score: 0
  fallback: true
  seed_reason: 未知类型保留语义正确的现有方案并补证据。
---

# 流水与同步 路由

根据 C2 冻结的方案和待实现变换，选择以下方法。保持算法、所有权和数值语义；越过 C2 自由度时返回重规划。

- [Prolog / steady / drain 与 queue/event 生命周期](recipes/pipeline.md)
- [Workspace 槽所有权与混合流水](recipes/slots.md)

- 按需回查 [sigmoid-pipeline](examples/sigmoid-pipeline.md) 的原协议和失败记录。

- 按需回查 [prefetch-boundaries](examples/prefetch-boundaries.md) 的原协议和失败记录。
