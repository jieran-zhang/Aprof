---
schema_version: aprof.knowledge-record/v1
id: edge.support.conflict.profile
kind: edge
version: 1.0.0
status: active
title: symptom.profile.ub_conflict_high → problem.ub_bank_conflict
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
  weight: 3
tags: []
seed_reason: 3 分：“Vector 的 UB 冲突计数偏高”支持“UB 布局引起 bank 冲突”；带完整判别条件的证据能直接区分机制。
relation: supports
from: symptom.profile.ub_conflict_high
to: problem.ub_bank_conflict
conditions: []
---

# symptom.profile.ub_conflict_high → problem.ub_bank_conflict

关系为 supports，专家排序初值为 3。3 分：“Vector 的 UB 冲突计数偏高”支持“UB 布局引起 bank 冲突”；带完整判别条件的证据能直接区分机制。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
