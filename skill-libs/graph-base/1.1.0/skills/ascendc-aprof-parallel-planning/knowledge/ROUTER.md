---
schema_version: aprof.knowledge-record/v1
id: planning.root
kind: router
version: 1.0.0
status: active
title: 并行规划知识入口
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-tiling-design/references/algorithm-families.md
  original_path: skills/ascendc-tiling-design/references/algorithm-families.md
  revision: aprof-1.1.0-pre-governance:sha256:9036a42db1a5c59c0df65aa065346ee5b6e0e951ac7e22f0522b96c8bfb3bd9b
  lines:
  - 1
  - 17
  sha256: sha256:9036a42db1a5c59c0df65aa065346ee5b6e0e951ac7e22f0522b96c8bfb3bd9b
  excerpt_sha256: sha256:9036a42db1a5c59c0df65aa065346ee5b6e0e951ac7e22f0522b96c8bfb3bd9b
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: null
references: []
evidence_status: source_reviewed_not_benchmarked
routes:
- target: planning.elementwise
  match:
  - field: family
    op: contains
    value: elementwise
  exclude: []
  required_evidence: []
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: planning.reduction
  match:
  - field: family
    op: contains
    value: reduction
  exclude: []
  required_evidence: []
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: planning.matmul
  match:
  - field: family
    op: contains
    value: matmul
  exclude: []
  required_evidence: []
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: planning.under-fusion
  match:
  - field: family
    op: contains
    value: under-fusion
  exclude: []
  required_evidence: []
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: planning.flash-attention
  match:
  - field: family
    op: contains
    value: flash-attention
  exclude: []
  required_evidence: []
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: planning.sort-topk
  match:
  - field: family
    op: contains
    value: sort-topk
  exclude: []
  required_evidence: []
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: planning.layout
  match:
  - field: family
    op: contains
    value: layout
  exclude: []
  required_evidence: []
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: planning.fallback
  match: []
  exclude: []
  required_evidence: []
  prior_score: 0
  fallback: true
  seed_reason: 未知类型保留语义正确的现有方案并补证据。
---

# 并行规划知识入口

从 C1 的 action 内容快照、算子 family、workload、语义和架构证据进入。只读取匹配的分支；一个算子可同时匹配算子族与欠融合模式。输出 C2，无需打开 diagnosis/graph。

- [Elementwise / Broadcast](families/elementwise/ROUTER.md)
- [Reduction / Norm / Softmax](families/reduction/ROUTER.md)
- [MatMul / GMM](families/matmul/ROUTER.md)
- [欠融合模式](families/under-fusion/ROUTER.md)
- [FlashAttention](families/flash-attention/ROUTER.md)
- [Sort / TopK](families/sort-topk/ROUTER.md)
- [布局转换](families/layout/ROUTER.md)
