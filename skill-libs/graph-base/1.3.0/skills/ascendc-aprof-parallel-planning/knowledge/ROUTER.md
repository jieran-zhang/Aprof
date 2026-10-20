---
schema_version: aprof.knowledge-record/v1
id: planning.root
kind: router
version: 1.1.0
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
- target: planning.indexing
  match:
  - field: family
    op: contains
    value: indexing
  exclude:
  - field: excluded_templates
    op: contains
    value: planning.indexing
  required_evidence: []
  prior_score: 3
  fallback: false
  seed_reason: 显式按算子族/技术类别进入；具体方法的前提由下一层核验。
- target: planning.moe-routing
  match:
  - field: family
    op: contains
    value: moe-routing
  exclude:
  - field: excluded_templates
    op: contains
    value: planning.moe-routing
  required_evidence: []
  prior_score: 3
  fallback: false
  seed_reason: 显式按算子族/技术类别进入；具体方法的前提由下一层核验。
---

# 并行规划知识入口

按 family 与 workload 选择任务划分、所有权和组合方案；可同时进入多个分支。比较适用主方案与保守回退，C2 输出必要内容快照、参数和实现自由度。

- [Elementwise / Broadcast 路由](families/elementwise/ROUTER.md)
- [Reduction / Norm / Softmax 路由](families/reduction/ROUTER.md)
- [MatMul / GMM 路由](families/matmul/ROUTER.md)
- [融合与组合模式](families/under-fusion/ROUTER.md)
- [FlashAttention 路由](families/flash-attention/ROUTER.md)
- [Sort / TopK 路由](families/sort-topk/ROUTER.md)
- [布局转换 路由](families/layout/ROUTER.md)
- [未覆盖算子族的通用方案](fallback.md)
- [索引访问与索引写入](families/indexing/ROUTER.md)
- [MoE 路由与结果回收组合](families/moe-routing/ROUTER.md)

来源审读不等于目标硬件收益验证；不确定的能力或容量返回 needs_evidence，不能由模板代填。
