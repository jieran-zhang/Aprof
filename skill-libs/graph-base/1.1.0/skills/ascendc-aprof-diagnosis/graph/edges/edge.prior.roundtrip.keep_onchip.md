---
schema_version: aprof.knowledge-record/v1
id: edge.prior.roundtrip.keep_onchip
kind: edge
version: 1.0.0
status: active
title: problem.redundant_gm_round_trip → action.keep_intermediate_onchip
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/optimization/references/data-movement-optimization-strategies.md
  original_path: skills/aprof/optimization/references/data-movement-optimization-strategies.md
  revision: aprof-1.1.0-pre-governance:sha256:5c3a68ff44e8f93f33ca3d6492c5b1894224e66b382e2e59fcb842b7e1086479
  lines:
  - 15
  - 24
  sha256: sha256:5c3a68ff44e8f93f33ca3d6492c5b1894224e66b382e2e59fcb842b7e1086479
  excerpt_sha256: sha256:442645c8d750d1f3edee4654d63a5c17fa7465142b9a4e54f5c6334b143b7151
learning:
  weight: 3
tags: []
seed_reason: 3 分：“保持中间结果片上驻留”直接消除“中间结果冗余 GM 往返”对应的重复或不均衡工作，前提由动作独立核验。
relation: mitigated_by
from: problem.redundant_gm_round_trip
to: action.keep_intermediate_onchip
conditions: []
---

# problem.redundant_gm_round_trip → action.keep_intermediate_onchip

关系为 mitigated_by，专家排序初值为 3。3 分：“保持中间结果片上驻留”直接消除“中间结果冗余 GM 往返”对应的重复或不均衡工作，前提由动作独立核验。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
