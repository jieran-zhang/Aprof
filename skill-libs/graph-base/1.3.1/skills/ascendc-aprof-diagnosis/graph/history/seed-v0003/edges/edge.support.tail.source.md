---
schema_version: aprof.knowledge-record/v1
id: edge.support.tail.source
kind: edge
version: 1.0.0
status: active
title: symptom.source.tail_concentrated → problem.core_tail_imbalance
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/diagnosis/references/ai-core-utilization-diagnosis-metrics.md
  original_path: skills/aprof/diagnosis/references/ai-core-utilization-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:0a70b21924e9ba29d6a75280699009b1f46afd4e9bd0fd3eb9880d592105e475
  lines:
  - 69
  - 75
  sha256: sha256:0a70b21924e9ba29d6a75280699009b1f46afd4e9bd0fd3eb9880d592105e475
  excerpt_sha256: sha256:151fee08eb7bb07239cd8a1efc85c9ad5e0ae8e81ba270bf63f767908c94e110
learning:
  weight: 3
tags: []
seed_reason: 3 分：“尾部工作集中到少量核”支持“尾块或核间工作失衡”；带完整判别条件的证据能直接区分机制。
relation: supports
from: symptom.source.tail_concentrated
to: problem.core_tail_imbalance
conditions: []
---

# symptom.source.tail_concentrated → problem.core_tail_imbalance

关系为 supports，专家排序初值为 3。3 分：“尾部工作集中到少量核”支持“尾块或核间工作失衡”；带完整判别条件的证据能直接区分机制。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
