---
schema_version: aprof.knowledge-record/v1
id: edge.support.vector.profile
kind: edge
version: 1.0.0
status: active
title: symptom.profile.vector_granularity_low → problem.vector_api_fragmentation
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
  - 58
  - 64
  sha256: sha256:7b5f46925a304a3d6db77c905675c8ecae3d12eeedeac501743bdc07f932d44e
  excerpt_sha256: sha256:8e89ada79f00c47215a93a0214ab24ee0e350adcc21bccb8cb2f914aa98750db
learning:
  weight: 2
tags: []
seed_reason: 2 分：“Vector 指令的有效处理粒度偏小”支持“Vector 调用碎片化”；有明确关联，仍需排除邻近机制或工作量解释。
relation: supports
from: symptom.profile.vector_granularity_low
to: problem.vector_api_fragmentation
conditions: []
---

# symptom.profile.vector_granularity_low → problem.vector_api_fragmentation

关系为 supports，专家排序初值为 2。2 分：“Vector 指令的有效处理粒度偏小”支持“Vector 调用碎片化”；有明确关联，仍需排除邻近机制或工作量解释。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
