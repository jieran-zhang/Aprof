---
schema_version: aprof.knowledge-record/v1
id: implementation.precision-boundaries
kind: router
version: 1.0.0
status: active
title: 精度与边界 路由
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/reduction/alg-welford.md
  original_path: ops/ascendc-tiling-design/references/reduction/alg-welford.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 74
  sha256: sha256:6c8e784dad546cb1caa07867596721b3d1c8ecc746396df5392054f44d84eb28
  excerpt_sha256: sha256:6c8e784dad546cb1caa07867596721b3d1c8ecc746396df5392054f44d84eb28
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: implementation.root
references: []
evidence_status: source_reviewed_not_benchmarked
routes:
- target: implementation.precision-boundaries.numeric
  match: []
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.precision-boundaries.numeric
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.plan_freedom
  - constraint.precision
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: implementation.precision-boundaries.bounds
  match: []
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.precision-boundaries.bounds
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.plan_freedom
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: implementation.precision-boundaries.fallback
  match: []
  exclude: []
  required_evidence: []
  prior_score: 0
  fallback: true
  seed_reason: 未知类型保留语义正确的现有方案并补证据。
---

# 精度与边界 路由

根据 C2 冻结的方案和待实现变换，选择以下方法。保持算法、所有权和数值语义；越过 C2 自由度时返回重规划。

- [累加精度、特殊值与数值边界](recipes/numeric.md)
- [Padding、容量和地址边界约束](recipes/bounds.md)
