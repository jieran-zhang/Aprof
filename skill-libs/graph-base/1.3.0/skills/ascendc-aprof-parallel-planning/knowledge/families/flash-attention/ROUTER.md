---
schema_version: aprof.knowledge-record/v1
id: planning.flash-attention
kind: router
version: 1.1.0
status: active
title: FlashAttention 路由
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/flashattention/design.md
  original_path: ops/ascendc-tiling-design/references/flashattention/design.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 634
  sha256: sha256:83ed347947ce330ed2940beb797be67fdc3cc30d60b9cf376d81711d76ab09cb
  excerpt_sha256: sha256:83ed347947ce330ed2940beb797be67fdc3cc30d60b9cf376d81711d76ab09cb
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.root
references: []
evidence_status: source_reviewed_not_benchmarked
routes:
- target: planning.flash-attention.online
  match: []
  exclude:
  - field: excluded_templates
    op: contains
    value: planning.flash-attention.online
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.softmax_semantics
  - constraint.task_ownership
  prior_score: 3
  fallback: false
  seed_reason: 直接适用的主方案，仍需所列语义/资源证据。
- target: planning.flash-attention.splitkv
  match:
  - field: features
    op: contains
    value: kv_underparallel
  exclude:
  - field: excluded_templates
    op: contains
    value: planning.flash-attention.splitkv
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.softmax_semantics
  - constraint.merge_semantics
  - constraint.workspace_ownership
  prior_score: 2
  fallback: false
  seed_reason: 满足所列适用特征后比较资源、同步与合并成本的条件性方案。
- target: planning.flash-attention.fallback
  match: []
  exclude: []
  required_evidence: []
  prior_score: 0
  fallback: true
  seed_reason: 未知类型保留语义正确的现有方案并补证据。
---

# FlashAttention 路由

按 family 与 workload 选择任务划分、所有权和组合方案；可同时进入多个分支。比较适用主方案与保守回退，C2 输出必要内容快照、参数和实现自由度。

- [Task 并行、KV streaming 与 online softmax](templates/online.md)
- [Decode split-KV 与稳定合并](templates/splitkv.md)
- [FlashAttention 通用回退](fallback.md)

来源审读不等于目标硬件收益验证；不确定的能力或容量返回 needs_evidence，不能由模板代填。
