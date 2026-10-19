---
schema_version: aprof.knowledge-record/v1
id: planning.sort-topk
kind: router
version: 1.0.0
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

比较下列方案的任务数、所有权、容量、额外流量、合并与同步成本。可返回多个候选，不用模板顺序代替 C2 的方案比较。

- [Sort/TopK 分块与层次归并](templates/merge.md)
