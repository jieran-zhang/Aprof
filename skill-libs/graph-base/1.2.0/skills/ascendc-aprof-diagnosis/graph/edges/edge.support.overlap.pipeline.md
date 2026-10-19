---
schema_version: aprof.knowledge-record/v1
id: edge.support.overlap.pipeline
kind: edge
version: 1.0.0
status: active
title: symptom.profile.overlap_low → problem.pipeline_serialization
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/diagnosis/references/bound-deep-routing.md
  original_path: skills/aprof/diagnosis/references/bound-deep-routing.md
  revision: aprof-1.1.0-pre-governance:sha256:7b5f46925a304a3d6db77c905675c8ecae3d12eeedeac501743bdc07f932d44e
  lines:
  - 83
  - 87
  sha256: sha256:7b5f46925a304a3d6db77c905675c8ecae3d12eeedeac501743bdc07f932d44e
  excerpt_sha256: sha256:3f1619f1c79c4f97938c9ee8866c29bdc50f8fd8749486e79626cf99c8ed6c1e
learning:
  weight: 2
tags: []
seed_reason: 2 分：“搬运与计算在时间线上缺少重叠”支持“搬运与计算串行”；有明确关联，仍需排除邻近机制或工作量解释。
relation: supports
from: symptom.profile.overlap_low
to: problem.pipeline_serialization
conditions: []
---

# symptom.profile.overlap_low → problem.pipeline_serialization

关系为 supports，专家排序初值为 2。2 分：“搬运与计算在时间线上缺少重叠”支持“搬运与计算串行”；有明确关联，仍需排除邻近机制或工作量解释。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
