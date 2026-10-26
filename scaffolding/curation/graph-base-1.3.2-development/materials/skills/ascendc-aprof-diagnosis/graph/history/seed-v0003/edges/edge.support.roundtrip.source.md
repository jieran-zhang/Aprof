---
schema_version: aprof.knowledge-record/v1
id: edge.support.roundtrip.source
kind: edge
version: 1.0.0
status: active
title: symptom.source.gm_intermediate_roundtrip → problem.redundant_gm_round_trip
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/diagnosis/references/source-hypothesis-routing.md
  original_path: skills/aprof/diagnosis/references/source-hypothesis-routing.md
  revision: aprof-1.1.0-pre-governance:sha256:ef273a362b02e6e2409ca55e684d55d5f54cf539529acb9154319b996090dd1c
  lines:
  - 33
  - 34
  sha256: sha256:ef273a362b02e6e2409ca55e684d55d5f54cf539529acb9154319b996090dd1c
  excerpt_sha256: sha256:9e03dce2658df561a46972d4234862cfb60fc8ca72489eaa2a52ed274d9ef8a5
learning:
  weight: 3
tags: []
seed_reason: 3 分：“本地生产消费的中间结果先写 GM 再读回”支持“中间结果冗余 GM 往返”；带完整判别条件的证据能直接区分机制。
relation: supports
from: symptom.source.gm_intermediate_roundtrip
to: problem.redundant_gm_round_trip
conditions: []
---

# symptom.source.gm_intermediate_roundtrip → problem.redundant_gm_round_trip

关系为 supports，专家排序初值为 3。3 分：“本地生产消费的中间结果先写 GM 再读回”支持“中间结果冗余 GM 往返”；带完整判别条件的证据能直接区分机制。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
