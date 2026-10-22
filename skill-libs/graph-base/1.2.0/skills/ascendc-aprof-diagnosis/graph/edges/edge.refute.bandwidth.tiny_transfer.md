---
schema_version: aprof.knowledge-record/v1
id: edge.refute.bandwidth.tiny_transfer
kind: edge
version: 1.0.0
status: active
title: symptom.profile.memory_bandwidth_saturation → problem.tiny_transfer_setup_amplification
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
  - 48
  - 48
  sha256: sha256:620c25b91946e0523ffc99aaddae20b8b6989d8b6a1474d7c15c49cb43bfbbbe
  excerpt_sha256: sha256:33c702652aa6f9cbbc51464f7c3f1818dbc4f5e623cfe6835bd3267de4b5407c
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/bound-deep-routing.md
  original_path: skills/ascendc-aprof-diagnosis/references/bound-deep-routing.md
  revision: aprof-1.1.0-pre-governance:sha256:620c25b91946e0523ffc99aaddae20b8b6989d8b6a1474d7c15c49cb43bfbbbe
  lines:
  - 49
  - 49
  sha256: sha256:620c25b91946e0523ffc99aaddae20b8b6989d8b6a1474d7c15c49cb43bfbbbe
  excerpt_sha256: sha256:d81c535798a3da2a772ebc3342b28508850152519efa0cd922cf3768f068a5a8
learning:
  weight: 3
tags: []
seed_reason: 3 分：已核验的“大块连续搬运接近已校准带宽上限”明确反对“小搬运放大发射开销”；字段缺失不能触发此反证。
relation: refutes
from: symptom.profile.memory_bandwidth_saturation
to: problem.tiny_transfer_setup_amplification
conditions: []
---

# symptom.profile.memory_bandwidth_saturation → problem.tiny_transfer_setup_amplification

关系为 refutes，专家排序初值为 3。3 分：已核验的“大块连续搬运接近已校准带宽上限”明确反对“小搬运放大发射开销”；字段缺失不能触发此反证。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
