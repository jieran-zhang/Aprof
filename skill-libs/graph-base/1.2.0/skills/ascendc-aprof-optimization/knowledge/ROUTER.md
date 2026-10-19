---
schema_version: aprof.knowledge-record/v1
id: implementation.root
kind: router
version: 1.0.0
status: active
title: 执行知识入口
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-perf-optimize/references/execution-mechanisms.md
  original_path: skills/ascendc-perf-optimize/references/execution-mechanisms.md
  revision: aprof-1.1.0-pre-governance:sha256:117f27ba6fb7cd69f3e5c6f32448b052d958a8e70e5c4dad044a34aa47aec071
  lines:
  - 1
  - 23
  sha256: sha256:117f27ba6fb7cd69f3e5c6f32448b052d958a8e70e5c4dad044a34aa47aec071
  excerpt_sha256: sha256:117f27ba6fb7cd69f3e5c6f32448b052d958a8e70e5c4dad044a34aa47aec071
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: null
references: []
evidence_status: source_reviewed_not_benchmarked
routes:
- target: implementation.tiling-tail
  match:
  - field: features
    op: contains
    value: tiling-tail
  exclude: []
  required_evidence: []
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: implementation.memory-transfer
  match:
  - field: features
    op: contains
    value: memory-transfer
  exclude: []
  required_evidence: []
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: implementation.buffer-lifetime
  match:
  - field: features
    op: contains
    value: buffer-lifetime
  exclude: []
  required_evidence: []
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: implementation.pipeline-sync
  match:
  - field: features
    op: contains
    value: pipeline-sync
  exclude: []
  required_evidence: []
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: implementation.vector-api
  match:
  - field: features
    op: contains
    value: vector-api
  exclude: []
  required_evidence: []
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: implementation.precision-boundaries
  match:
  - field: features
    op: contains
    value: precision-boundaries
  exclude: []
  required_evidence: []
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: implementation.fallback
  match: []
  exclude: []
  required_evidence: []
  prior_score: 0
  fallback: true
  seed_reason: 未知类型保留语义正确的现有方案并补证据。
---

# 执行知识入口

只使用 C2 的方案、action/模板快照和实现约束；不重新运行诊断图，也不重新做算法规划。features 可以同时命中多个执行分支。

- [Tiling / tail](branches/tiling-tail/ROUTER.md)
- [搬运与写回](branches/memory-transfer/ROUTER.md)
- [Buffer 存活期与布局](branches/buffer-lifetime/ROUTER.md)
- [流水与同步](branches/pipeline-sync/ROUTER.md)
- [Vector / API](branches/vector-api/ROUTER.md)
- [精度与边界](branches/precision-boundaries/ROUTER.md)
