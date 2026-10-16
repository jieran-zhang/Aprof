---
schema_version: aprof.knowledge-record/v1
id: planning.elementwise.fallback
kind: strategy
version: 1.0.0
status: active
title: Elementwise / Broadcast 通用回退
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
parent: planning.elementwise
references: []
evidence_status: source_reviewed_not_benchmarked
---

# Elementwise / Broadcast 通用回退

保留已验证的基线算法和输出所有权，记录当前缺失的容量、语义或 API 依据。新模板无法满足容量、精度或任务覆盖时退回该实现，不能用未验证方案填补缺项。C2 必须给出实际 fallback entry/key 和互斥元数据域。
