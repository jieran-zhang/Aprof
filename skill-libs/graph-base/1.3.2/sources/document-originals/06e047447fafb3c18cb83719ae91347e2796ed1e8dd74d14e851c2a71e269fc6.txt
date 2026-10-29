---
schema_version: aprof.knowledge-record/v1
id: implementation.buffer-lifetime
kind: router
version: 1.1.0
status: active
title: Buffer 存活期与布局 路由
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/ops/ascendc-performance-best-practices/reference/common/ub_resident_design.md
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
parent: implementation.root
references: []
evidence_status: source_reviewed_not_benchmarked
routes:
- target: implementation.buffer-lifetime.reuse
  match: []
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.buffer-lifetime.reuse
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.plan_freedom
  - constraint.dependency_lifetime
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: implementation.buffer-lifetime.example.ub-accumulator
  match:
  - field: examples
    op: contains
    value: ub-accumulator
  exclude: []
  required_evidence: []
  prior_score: 1
  fallback: false
  seed_reason: 探索性参照，需要额外证据。
- target: implementation.buffer-lifetime.fallback
  match: []
  exclude: []
  required_evidence: []
  prior_score: 0
  fallback: true
  seed_reason: 未知类型保留语义正确的现有方案并补证据。
- target: implementation.buffer-lifetime.arch22-bank-layout
  match: []
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.buffer-lifetime.arch22-bank-layout
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.plan_freedom
  - constraint.target_api
  - constraint.dependency_lifetime
  prior_score: 2
  fallback: false
  seed_reason: 属于本分支的条件性方案；先核验正文的能力、语义和资源前提，再比较成本。
---

# Buffer 存活期与布局 路由

按 C2 冻结的方案与 features 选择实现技巧；可同时进入多个分支。保持算法、所有权和数值契约；超出已声明自由度时请求重规划。

- [存活期、合法复用与 UB 布局核验](recipes/reuse.md)
- [UB 累加器消除逐 tile scalar 反馈的历史反例](examples/ub-accumulator.md)
- [Buffer 存活期与布局 回退方法](fallback.md)
- [arch22 UB bank 地址、padding 与 repeat 联合布局](recipes/arch22-bank-layout.md)

来源审读不等于目标硬件收益验证；不确定的能力或容量返回 needs_evidence，不能由模板代填。
