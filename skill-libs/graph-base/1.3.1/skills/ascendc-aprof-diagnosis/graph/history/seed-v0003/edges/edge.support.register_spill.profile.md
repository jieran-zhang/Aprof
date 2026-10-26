---
schema_version: aprof.knowledge-record/v1
id: edge.support.register_spill.profile
kind: edge
version: 1.0.0
status: active
title: symptom.profile.register_spill → problem.register_spill
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/bound-deep-routing.md
  original_path: skills/ascendc-aprof-diagnosis/references/bound-deep-routing.md
  revision: aprof-1.1.0-pre-governance:sha256:620c25b91946e0523ffc99aaddae20b8b6989d8b6a1474d7c15c49cb43bfbbbe
  lines:
  - 36
  - 36
  sha256: sha256:620c25b91946e0523ffc99aaddae20b8b6989d8b6a1474d7c15c49cb43bfbbbe
  excerpt_sha256: sha256:7d686e034229907a1aa618783bf9a57377656b6b26806363f1a39ae44b8422d2
learning:
  weight: 3
tags: []
seed_reason: 3 分：“编译报告或指令跟踪确认非算法必要的 spill/LoadStore”支持“寄存器压力引发 spill”；带完整判别条件的证据能直接区分机制。
relation: supports
from: symptom.profile.register_spill
to: problem.register_spill
conditions: []
---

# symptom.profile.register_spill → problem.register_spill

关系为 supports，专家排序初值为 3。3 分：“编译报告或指令跟踪确认非算法必要的 spill/LoadStore”支持“寄存器压力引发 spill”；带完整判别条件的证据能直接区分机制。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
