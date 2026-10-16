---
schema_version: aprof.knowledge-record/v1
id: edge.support.roundtrip.profile
kind: edge
version: 1.0.0
status: active
title: symptom.profile.gm_traffic_amplified → problem.redundant_gm_round_trip
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
  - 48
  - 55
  sha256: sha256:9bf71febdfee0429bc107731ac339a59941e55f0aeed27cd0030a4cd1ec5aaa2
  excerpt_sha256: sha256:8e434e79101ba142ba0f35025e347203b6d519ddaa5fc1a9f719708dc04d19c1
learning:
  weight: 2
tags: []
seed_reason: 2 分：“实测 GM 流量高于算法下界”支持“中间结果冗余 GM 往返”；有明确关联，仍需排除邻近机制或工作量解释。
relation: supports
from: symptom.profile.gm_traffic_amplified
to: problem.redundant_gm_round_trip
conditions: []
---

# symptom.profile.gm_traffic_amplified → problem.redundant_gm_round_trip

关系为 supports，专家排序初值为 2。2 分：“实测 GM 流量高于算法下界”支持“中间结果冗余 GM 往返”；有明确关联，仍需排除邻近机制或工作量解释。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
