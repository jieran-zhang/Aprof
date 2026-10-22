---
schema_version: aprof.knowledge-record/v1
id: planning.under-fusion.fallback
kind: strategy
version: 1.0.0
status: active
title: 欠融合模式 通用回退
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-performance-best-practices/reference/common/ub_resident_design.md
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
parent: planning.under-fusion
references: []
evidence_status: source_reviewed_not_benchmarked
---

# 欠融合模式 通用回退

保留已验证的基线算法和输出所有权，记录当前缺失的容量、语义或 API 依据。新模板无法满足容量、精度或任务覆盖时退回该实现，不能用未验证方案填补缺项。C2 必须给出实际 fallback entry/key 和互斥元数据域。
