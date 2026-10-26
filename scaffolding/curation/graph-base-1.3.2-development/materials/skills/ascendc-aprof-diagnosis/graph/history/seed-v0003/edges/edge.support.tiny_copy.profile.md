---
schema_version: aprof.knowledge-record/v1
id: edge.support.tiny_copy.profile
kind: edge
version: 1.0.0
status: active
title: symptom.profile.mte_setup_dominated → problem.tiny_transfer_setup_amplification
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
  - 46
  - 51
  sha256: sha256:7b5f46925a304a3d6db77c905675c8ecae3d12eeedeac501743bdc07f932d44e
  excerpt_sha256: sha256:a2be289520d72c7e7723e6d6dfb7fe1cde47c924097dfb4347c8a2e2fdaa3477
learning:
  weight: 3
tags: []
seed_reason: 3 分：“MTE 占比高且单位指令有效搬运小、带宽低”支持“小搬运放大发射开销”；带完整判别条件的证据能直接区分机制。
relation: supports
from: symptom.profile.mte_setup_dominated
to: problem.tiny_transfer_setup_amplification
conditions: []
---

# symptom.profile.mte_setup_dominated → problem.tiny_transfer_setup_amplification

关系为 supports，专家排序初值为 3。3 分：“MTE 占比高且单位指令有效搬运小、带宽低”支持“小搬运放大发射开销”；带完整判别条件的证据能直接区分机制。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
