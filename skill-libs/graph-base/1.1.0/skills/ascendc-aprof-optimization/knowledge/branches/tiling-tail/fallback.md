---
schema_version: aprof.knowledge-record/v1
id: implementation.tiling-tail.fallback
kind: recipe
version: 1.0.0
status: active
title: Tiling / tail 回退方法
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  original_path: ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 151
  sha256: sha256:c74ad927867806d42723213292831e22c84a2e84d75230e5aa615dee1500782a
  excerpt_sha256: sha256:c74ad927867806d42723213292831e22c84a2e84d75230e5aa615dee1500782a
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: implementation.tiling-tail
references: []
evidence_status: source_reviewed_not_benchmarked
---

# Tiling / tail 回退方法

保留当前正确实现，逐项确认 C2 参数与 API 支持。不能满足前提时记录失败和缺项，调用相应辅助技能；不要绕过所有权、容量或精度边界。验证使用原 oracle 全 case，性能结果不能覆盖正确性失败。
