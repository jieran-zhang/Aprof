---
schema_version: aprof.knowledge-record/v1
id: implementation.tiling-tail
kind: router
version: 1.1.0
status: active
title: Tiling / tail 路由
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/reduction/ar-fullload.md
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
parent: implementation.root
references: []
evidence_status: source_reviewed_not_benchmarked
routes:
- target: implementation.tiling-tail.valid-length
  match: []
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.tiling-tail.valid-length
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.plan_freedom
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: implementation.tiling-tail.dispatch
  match: []
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.tiling-tail.dispatch
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.plan_freedom
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: implementation.tiling-tail.example.exp-tile8192
  match:
  - field: examples
    op: contains
    value: exp-tile8192
  exclude: []
  required_evidence: []
  prior_score: 1
  fallback: false
  seed_reason: 探索性参照，需要额外证据。
- target: implementation.tiling-tail.fallback
  match: []
  exclude: []
  required_evidence: []
  prior_score: 0
  fallback: true
  seed_reason: 未知类型保留语义正确的现有方案并补证据。
---

# Tiling / tail 路由

按 C2 冻结的方案与 features 选择实现技巧；可同时进入多个分支。保持算法、所有权和数值契约；超出已声明自由度时请求重规划。

- [有效长度、对齐长度与动态尾块](recipes/valid-length.md)
- [元数据分发与实现身份接线](recipes/dispatch.md)
- [exp 在固定并行划分内将 tile 从4096增至8192](examples/exp-tile8192.md)
- [Tiling / tail 回退方法](fallback.md)

来源审读不等于目标硬件收益验证；不确定的能力或容量返回 needs_evidence，不能由模板代填。
