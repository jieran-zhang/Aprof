---
schema_version: aprof.knowledge-record/v1
id: edge.action.insufficient_input_reuse
kind: edge
version: 1.0.0
status: active
title: problem.insufficient_input_reuse → action.reuse_input_tiles
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/data-movement-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/data-movement-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:58e28c093db98279fc16b45d1140c4673e3f9b312392618908c515bdc58b04e3
  lines:
  - 67
  - 67
  sha256: sha256:58e28c093db98279fc16b45d1140c4673e3f9b312392618908c515bdc58b04e3
  excerpt_sha256: sha256:a374c2ad0072ec617e1ee3f8b5854465e2148afe3fcb4cfa3215c9d6dc2ce37c
learning:
  weight: 3
tags: []
seed_reason: 3 分：“在容量允许时复用输入块”直接消除“重复输入未复用”对应的重复或不均衡工作，前提由动作独立核验。
relation: mitigated_by
from: problem.insufficient_input_reuse
to: action.reuse_input_tiles
conditions: []
---

# problem.insufficient_input_reuse → action.reuse_input_tiles

关系为 mitigated_by，专家排序初值为 3。3 分：“在容量允许时复用输入块”直接消除“重复输入未复用”对应的重复或不均衡工作，前提由动作独立核验。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
