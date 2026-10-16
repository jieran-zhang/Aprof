---
schema_version: aprof.knowledge-record/v1
id: planning.fallback
kind: strategy
version: 1.0.0
status: active
title: 未覆盖算子族的通用方案
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
parent: planning.root
references: []
evidence_status: source_reviewed_not_benchmarked
---

# 未覆盖算子族的通用方案

将算子分解为已知子操作，保留原始语义和有效实现。优先恢复任务所有权、资源预算与 fallback；没有专属模板时不能虚构硬件结论。Random/Convolution 等可引用相关子操作模板，专属性能结论保持未知。
