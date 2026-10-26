---
schema_version: aprof.knowledge-record/v1
id: planning.elementwise
kind: router
version: 1.1.0
status: active
title: Elementwise / Broadcast 路由
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/elewise/tiling.md
  original_path: ops/ascendc-tiling-design/references/elewise/tiling.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 215
  sha256: sha256:40fd7187bf84f9c454fc5a53b0c5adc1e9594e6054901f21c518cae1ee3ad0ad
  excerpt_sha256: sha256:40fd7187bf84f9c454fc5a53b0c5adc1e9594e6054901f21c518cae1ee3ad0ad
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.root
references: []
evidence_status: source_reviewed_not_benchmarked
routes:
- target: planning.elementwise.continuous
  match: []
  exclude:
  - field: excluded_templates
    op: contains
    value: planning.elementwise.continuous
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.task_ownership
  - constraint.valid_lengths
  prior_score: 3
  fallback: false
  seed_reason: 直接适用的主方案，仍需所列语义/资源证据。
- target: planning.elementwise.broadcast
  match:
  - field: features
    op: contains
    value: broadcast
  exclude:
  - field: excluded_templates
    op: contains
    value: planning.elementwise.broadcast
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.broadcast_semantics
  - constraint.reuse_domain
  prior_score: 2
  fallback: false
  seed_reason: 满足所列适用特征后比较资源、同步与合并成本的条件性方案。
- target: planning.elementwise.fallback
  match: []
  exclude: []
  required_evidence: []
  prior_score: 0
  fallback: true
  seed_reason: 未知类型保留语义正确的现有方案并补证据。
---

# Elementwise / Broadcast 路由

按 family 与 workload 选择任务划分、所有权和组合方案；可同时进入多个分支。比较适用主方案与保守回退，C2 输出必要内容快照、参数和实现自由度。

- [连续输出分区与均衡尾块](templates/continuous.md)
- [广播复用与容量分块](templates/broadcast.md)
- [Elementwise / Broadcast 通用回退](fallback.md)

来源审读不等于目标硬件收益验证；不确定的能力或容量返回 needs_evidence，不能由模板代填。
