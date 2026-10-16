---
schema_version: aprof.knowledge-record/v1
id: planning.reduction
kind: router
version: 1.0.0
status: active
title: Reduction / Norm / Softmax 路由
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  original_path: ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 151
  sha256: sha256:c74ad927867806d42723213292831e22c84a2e84d75230e5aa615dee1500782a
  excerpt_sha256: sha256:c74ad927867806d42723213292831e22c84a2e84d75230e5aa615dee1500782a
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.root
references: []
evidence_status: source_reviewed_not_benchmarked
routes:
- target: planning.reduction.fullload
  match: []
  exclude:
  - field: excluded_templates
    op: contains
    value: planning.reduction.fullload
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.reduction_semantics
  - constraint.full_load
  prior_score: 3
  fallback: false
  seed_reason: 直接适用的主方案，仍需所列语义/资源证据。
- target: planning.reduction.split
  match: []
  exclude:
  - field: excluded_templates
    op: contains
    value: planning.reduction.split
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.reduction_semantics
  - constraint.merge_semantics
  prior_score: 2
  fallback: false
  seed_reason: 满足所列适用特征后比较资源、同步与合并成本的条件性方案。
- target: planning.reduction.statistics
  match:
  - field: features
    op: contains
    value: statistics
  exclude:
  - field: excluded_templates
    op: contains
    value: planning.reduction.statistics
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.reduction_semantics
  - constraint.precision
  prior_score: 2
  fallback: false
  seed_reason: 满足所列适用特征后比较资源、同步与合并成本的条件性方案。
- target: planning.reduction.example.norm-partials
  match:
  - field: examples
    op: contains
    value: norm-partials
  exclude: []
  required_evidence: []
  prior_score: 1
  fallback: false
  seed_reason: 探索性参照，需要额外证据。
- target: planning.reduction.example.norm-p-specialization
  match:
  - field: examples
    op: contains
    value: norm-p-specialization
  exclude: []
  required_evidence: []
  prior_score: 1
  fallback: false
  seed_reason: 探索性参照，需要额外证据。
- target: planning.reduction.fallback
  match: []
  exclude: []
  required_evidence: []
  prior_score: 0
  fallback: true
  seed_reason: 未知类型保留语义正确的现有方案并补证据。
---

# Reduction / Norm / Softmax 路由

比较下列方案的任务数、所有权、容量、额外流量、合并与同步成本。可返回多个候选，不用模板顺序代替 C2 的方案比较。

- [AR/ARA FullLoad 与行所有权](templates/fullload.md)
- [ColSplit/RowSplit 与分段合并](templates/split.md)
- [方差、Norm 与 Softmax 数值状态](templates/statistics.md)

- 按需回查 [norm-partials](examples/norm-partials.md) 的原协议和失败记录。

- 按需回查 [norm-p-specialization](examples/norm-p-specialization.md) 的原协议和失败记录。
