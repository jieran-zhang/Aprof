---
schema_version: aprof.knowledge-record/v1
id: implementation.fallback
kind: recipe
version: 1.0.0
status: active
title: 执行通用回退
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
parent: implementation.root
references: []
evidence_status: source_reviewed_not_benchmarked
---

# 执行通用回退

在 C2 的参数边界内保持已有正确实现，恢复有效长度、容量、所有权与同步证明。若无合适方法则记录知识缺口，不发明性能收益；提供源码差异、构建和完整正确性结果后再决定是否计时。
