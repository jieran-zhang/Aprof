---
schema_version: aprof.knowledge-record/v1
id: planning.matmul
kind: router
version: 1.0.0
status: active
title: MatMul / GMM 路由
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/matmul/ascendc-api-gmm-tiling.md
  original_path: ops/ascendc-tiling-design/references/matmul/ascendc-api-gmm-tiling.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 313
  sha256: sha256:90d9b2c693a9fb876326157a618e383413c28cf660e8d4f92941a96b6c593cb1
  excerpt_sha256: sha256:90d9b2c693a9fb876326157a618e383413c28cf660e8d4f92941a96b6c593cb1
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.root
references: []
evidence_status: source_reviewed_not_benchmarked
routes:
- target: planning.matmul.mn
  match: []
  exclude:
  - field: excluded_templates
    op: contains
    value: planning.matmul.mn
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.task_ownership
  - constraint.l1_l0_budget
  prior_score: 3
  fallback: false
  seed_reason: 直接适用的主方案，仍需所列语义/资源证据。
- target: planning.matmul.resident
  match:
  - field: features
    op: contains
    value: reusable_matrix_side
  exclude:
  - field: excluded_templates
    op: contains
    value: planning.matmul.resident
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.l1_l0_budget
  - constraint.reuse_domain
  prior_score: 2
  fallback: false
  seed_reason: 满足所列适用特征后比较资源、同步与合并成本的条件性方案。
- target: planning.matmul.splitk
  match:
  - field: features
    op: contains
    value: long_k_underparallel
  exclude:
  - field: excluded_templates
    op: contains
    value: planning.matmul.splitk
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.merge_semantics
  - constraint.workspace_ownership
  - constraint.precision
  prior_score: 2
  fallback: false
  seed_reason: 满足所列适用特征后比较资源、同步与合并成本的条件性方案。
- target: planning.matmul.fallback
  match: []
  exclude: []
  required_evidence: []
  prior_score: 0
  fallback: true
  seed_reason: 未知类型保留语义正确的现有方案并补证据。
---

# MatMul / GMM 路由

比较下列方案的任务数、所有权、容量、额外流量、合并与同步成本。可返回多个候选，不用模板顺序代替 C2 的方案比较。

- [MN 分块与 GMM 负载均衡](templates/mn.md)
- [小侧驻留与 L1/L0 复用](templates/resident.md)
- [split-K/StreamK 与部分结果合并](templates/splitk.md)
