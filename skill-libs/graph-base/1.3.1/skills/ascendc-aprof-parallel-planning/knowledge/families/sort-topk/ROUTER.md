---
schema_version: aprof.knowledge-record/v1
id: planning.sort-topk
kind: router
version: 1.1.0
status: active
title: Sort / TopK 路由
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/sort/alg-two-level-mrgsort.md
  original_path: ops/ascendc-tiling-design/references/sort/alg-two-level-mrgsort.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 681
  sha256: sha256:031b9829393ccd4f83ca8cd19d8a6ce47d42274e2975c247d487e9d87edcdcf6
  excerpt_sha256: sha256:031b9829393ccd4f83ca8cd19d8a6ce47d42274e2975c247d487e9d87edcdcf6
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.root
references: []
evidence_status: source_reviewed_not_benchmarked
routes:
- target: planning.sort-topk.merge
  match: []
  exclude:
  - field: excluded_templates
    op: contains
    value: planning.sort-topk.merge
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.sort_semantics
  - constraint.merge_semantics
  prior_score: 3
  fallback: false
  seed_reason: 直接适用的主方案，仍需所列语义/资源证据。
- target: planning.sort-topk.fallback
  match: []
  exclude: []
  required_evidence: []
  prior_score: 0
  fallback: true
  seed_reason: 未知类型保留语义正确的现有方案并补证据。
---

# Sort / TopK 路由

按 family 与 workload 选择任务划分、所有权和组合方案；可同时进入多个分支。比较适用主方案与保守回退，C2 输出必要内容快照、参数和实现自由度。

- [Sort/TopK 分块与层次归并](templates/merge.md)
- [Sort / TopK 通用回退](fallback.md)

来源审读不等于目标硬件收益验证；不确定的能力或容量返回 needs_evidence，不能由模板代填。
