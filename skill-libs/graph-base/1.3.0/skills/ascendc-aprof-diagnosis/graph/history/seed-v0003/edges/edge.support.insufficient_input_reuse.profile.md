---
schema_version: aprof.knowledge-record/v1
id: edge.support.insufficient_input_reuse.profile
kind: edge
version: 1.0.0
status: active
title: symptom.profile.insufficient_input_reuse → problem.insufficient_input_reuse
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
  weight: 2
tags: []
seed_reason: 2 分：“输入流量高于按复用次数计算的下界”支持“重复输入未复用”；有明确关联，仍需排除邻近机制或工作量解释。
relation: supports
from: symptom.profile.insufficient_input_reuse
to: problem.insufficient_input_reuse
conditions: []
---

# symptom.profile.insufficient_input_reuse → problem.insufficient_input_reuse

关系为 supports，专家排序初值为 2。2 分：“输入流量高于按复用次数计算的下界”支持“重复输入未复用”；有明确关联，仍需排除邻近机制或工作量解释。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
