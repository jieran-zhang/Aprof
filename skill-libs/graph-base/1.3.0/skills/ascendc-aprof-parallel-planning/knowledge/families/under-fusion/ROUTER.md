---
schema_version: aprof.knowledge-record/v1
id: planning.under-fusion
kind: router
version: 1.1.0
status: active
title: 融合与组合模式
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-performance-best-practices/reference/common/ub_resident_design.md
  original_path: ops/ascendc-performance-best-practices/reference/common/ub_resident_design.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 342
  sha256: sha256:422c329fdf4dcb62d095afc88371f7bb44f51aa624398cc977cdc0e995b8d5e3
  excerpt_sha256: sha256:422c329fdf4dcb62d095afc88371f7bb44f51aa624398cc977cdc0e995b8d5e3
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.root
references: []
evidence_status: source_reviewed_not_benchmarked
routes:
- target: planning.under-fusion.vector_producer_consumer
  match: []
  exclude:
  - field: excluded_templates
    op: contains
    value: planning.under-fusion.vector_producer_consumer
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.plan_freedom
  - constraint.dependency_lifetime
  - constraint.target_api
  prior_score: 2
  fallback: false
  seed_reason: 仅既有分支内的条件候选；正文适用域和成本仍须核验，不强制优先。
- target: planning.under-fusion.chain
  match: []
  exclude:
  - field: excluded_templates
    op: contains
    value: planning.under-fusion.chain
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.fusion_boundary
  - constraint.dependency_lifetime
  prior_score: 3
  fallback: false
  seed_reason: 直接适用的主方案，仍需所列语义/资源证据。
- target: planning.under-fusion.reduce_broadcast
  match:
  - field: features
    op: contains
    value: reduce_broadcast
  exclude:
  - field: excluded_templates
    op: contains
    value: planning.under-fusion.reduce_broadcast
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.reduction_semantics
  - constraint.fusion_boundary
  prior_score: 2
  fallback: false
  seed_reason: 满足所列适用特征后比较资源、同步与合并成本的条件性方案。
- target: planning.under-fusion.epilogue
  match:
  - field: features
    op: contains
    value: matmul_epilogue
  exclude:
  - field: excluded_templates
    op: contains
    value: planning.under-fusion.epilogue
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.fusion_boundary
  - constraint.cross_engine_dependencies
  prior_score: 2
  fallback: false
  seed_reason: 满足所列适用特征后比较资源、同步与合并成本的条件性方案。
- target: planning.under-fusion.fallback
  match: []
  exclude: []
  required_evidence: []
  prior_score: 0
  fallback: true
  seed_reason: 未知类型保留语义正确的现有方案并补证据。
---
# 融合与组合模式

按 family 与 workload 选择任务划分、所有权和组合方案；可同时进入多个分支。比较适用主方案与保守回退，C2 输出必要内容快照、参数和实现自由度。

- [融合与组合：连续逐元素链](templates/chain.md)
- [融合与组合：归约后广播](templates/reduce_broadcast.md)
- [融合与组合：MatMul 输出后处理](templates/epilogue.md)
- [融合与组合通用回退](fallback.md)

来源审读不等于目标硬件收益验证；不确定的能力或容量返回 needs_evidence，不能由模板代填。
