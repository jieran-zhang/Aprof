---
schema_version: aprof.knowledge-record/v1
id: edge.support.scalar.source
kind: edge
version: 1.0.0
status: active
title: symptom.source.scalar_element_loop → problem.scalar_control_hot_loop
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
  - 59
  - 64
  sha256: sha256:9bf71febdfee0429bc107731ac339a59941e55f0aeed27cd0030a4cd1ec5aaa2
  excerpt_sha256: sha256:7b98a326c095ef5c96fdf900a3078995b4ea17a69d59264ce0f91dbc81b0cb05
learning:
  weight: 3
tags: []
seed_reason: 3 分：“逐元素循环调用标量读写或算术”支持“标量逐元素热循环”；带完整判别条件的证据能直接区分机制。
relation: supports
from: symptom.source.scalar_element_loop
to: problem.scalar_control_hot_loop
conditions: []
---

# symptom.source.scalar_element_loop → problem.scalar_control_hot_loop

关系为 supports，专家排序初值为 3。3 分：“逐元素循环调用标量读写或算术”支持“标量逐元素热循环”；带完整判别条件的证据能直接区分机制。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
