---
schema_version: aprof.knowledge-record/v1
id: edge.support.scalar.profile
kind: edge
version: 1.0.0
status: active
title: symptom.profile.scalar_hot → problem.scalar_control_hot_loop
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/diagnosis/references/api-algorithm-diagnosis-metrics.md
  original_path: skills/aprof/diagnosis/references/api-algorithm-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:9bf71febdfee0429bc107731ac339a59941e55f0aeed27cd0030a4cd1ec5aaa2
  lines:
  - 20
  - 27
  sha256: sha256:9bf71febdfee0429bc107731ac339a59941e55f0aeed27cd0030a4cd1ec5aaa2
  excerpt_sha256: sha256:5ec6c11909cb2414cbb1b84e85c09c41cbcbc71207791a5f8fddf5340c143040
learning:
  weight: 2
tags: []
seed_reason: 2 分：“有效工作区间 Scalar 时间占比高”支持“标量逐元素热循环”；有明确关联，仍需排除邻近机制或工作量解释。
relation: supports
from: symptom.profile.scalar_hot
to: problem.scalar_control_hot_loop
conditions: []
---

# symptom.profile.scalar_hot → problem.scalar_control_hot_loop

关系为 supports，专家排序初值为 2。2 分：“有效工作区间 Scalar 时间占比高”支持“标量逐元素热循环”；有明确关联，仍需排除邻近机制或工作量解释。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
