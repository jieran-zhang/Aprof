---
schema_version: aprof.knowledge-record/v1
id: implementation.buffer-lifetime.fallback
kind: recipe
version: 1.0.0
status: active
title: Buffer 存活期与布局 回退方法
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/ops/ascendc-performance-best-practices/reference/common/ub_resident_design.md
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
parent: implementation.buffer-lifetime
references: []
evidence_status: source_reviewed_not_benchmarked
---

# Buffer 存活期与布局 回退方法

保留当前正确实现，逐项确认 C2 参数与 API 支持。不能满足前提时记录失败和缺项，调用相应辅助技能；不要绕过所有权、容量或精度边界。验证使用原 oracle 全 case，性能结果不能覆盖正确性失败。
