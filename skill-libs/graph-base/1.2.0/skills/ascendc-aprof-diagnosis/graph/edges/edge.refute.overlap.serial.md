---
schema_version: aprof.knowledge-record/v1
id: edge.refute.overlap.serial
kind: edge
version: 1.0.0
status: active
title: symptom.profile.steady_overlap → problem.pipeline_serialization
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
  - 51
  - 51
  sha256: sha256:620c25b91946e0523ffc99aaddae20b8b6989d8b6a1474d7c15c49cb43bfbbbe
  excerpt_sha256: sha256:331f86446b51f0a01e94aa03f7a1c1ad4171450ad5025d79ef7805815f2c5851
learning:
  weight: 3
tags: []
seed_reason: 3 分：已核验的“时间线上存在稳定的搬运计算重叠”明确反对“搬运与计算串行”；字段缺失不能触发此反证。
relation: refutes
from: symptom.profile.steady_overlap
to: problem.pipeline_serialization
conditions: []
---

# symptom.profile.steady_overlap → problem.pipeline_serialization

关系为 refutes，专家排序初值为 3。3 分：已核验的“时间线上存在稳定的搬运计算重叠”明确反对“搬运与计算串行”；字段缺失不能触发此反证。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
