---
schema_version: aprof.knowledge-record/v1
id: implementation.root
kind: router
version: 1.1.0
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
- target: implementation.cube-api
  match:
  - field: features
    op: contains
    value: cube-api
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.cube-api
  required_evidence: []
  prior_score: 3
  fallback: false
  seed_reason: 显式按算子族/技术类别进入；具体方法的前提由下一层核验。
- target: implementation.fusion-composition
  match:
  - field: features
    op: contains
    value: fusion-composition
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.fusion-composition
  required_evidence: []
  prior_score: 3
  fallback: false
  seed_reason: 显式按算子族/技术类别进入；具体方法的前提由下一层核验。
- target: implementation.scalar-control
  match:
  - field: features
    op: contains
    value: scalar-control
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.scalar-control
  required_evidence: []
  prior_score: 3
  fallback: false
  seed_reason: 显式按算子族/技术类别进入；具体方法的前提由下一层核验。
---

# 执行知识入口

按 C2 冻结的方案与 features 选择实现技巧；可同时进入多个分支。保持算法、所有权和数值契约；超出已声明自由度时请求重规划。

- [Tiling / tail 路由](branches/tiling-tail/ROUTER.md)
- [搬运与写回 路由](branches/memory-transfer/ROUTER.md)
- [Buffer 存活期与布局 路由](branches/buffer-lifetime/ROUTER.md)
- [流水与同步 路由](branches/pipeline-sync/ROUTER.md)
- [Vector / API 路由](branches/vector-api/ROUTER.md)
- [精度与边界 路由](branches/precision-boundaries/ROUTER.md)
- [执行通用回退](fallback.md)
- [Cube / Matmul 计算执行](branches/cube-api/ROUTER.md)
- [算子组合与 Cube–Vector 交接](branches/fusion-composition/ROUTER.md)
- [标量、地址与控制开销](branches/scalar-control/ROUTER.md)

来源审读不等于目标硬件收益验证；不确定的能力或容量返回 needs_evidence，不能由模板代填。
