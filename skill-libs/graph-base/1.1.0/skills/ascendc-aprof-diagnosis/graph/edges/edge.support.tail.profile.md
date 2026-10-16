---
schema_version: aprof.knowledge-record/v1
id: edge.support.tail.profile
kind: edge
version: 1.0.0
status: active
title: symptom.profile.per_core_time_imbalanced → problem.core_tail_imbalance
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
  - 30
  - 37
  sha256: sha256:0a70b21924e9ba29d6a75280699009b1f46afd4e9bd0fd3eb9880d592105e475
  excerpt_sha256: sha256:3bd9517086fefd028024536594fd0ba0c44622d7f69b129798a97fee5d1c6618
learning:
  weight: 2
tags: []
seed_reason: 2 分：“同次调用的逐核耗时不均”支持“尾块或核间工作失衡”；有明确关联，仍需排除邻近机制或工作量解释。
relation: supports
from: symptom.profile.per_core_time_imbalanced
to: problem.core_tail_imbalance
conditions: []
---

# symptom.profile.per_core_time_imbalanced → problem.core_tail_imbalance

关系为 supports，专家排序初值为 2。2 分：“同次调用的逐核耗时不均”支持“尾块或核间工作失衡”；有明确关联，仍需排除邻近机制或工作量解释。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
