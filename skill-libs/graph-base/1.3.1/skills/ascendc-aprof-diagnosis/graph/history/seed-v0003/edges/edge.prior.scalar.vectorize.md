---
schema_version: aprof.knowledge-record/v1
id: edge.prior.scalar.vectorize
kind: edge
version: 1.0.0
status: active
title: problem.scalar_control_hot_loop → action.vectorize_scalar_loop
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/optimization/references/api-algorithm-optimization-strategies.md
  original_path: skills/aprof/optimization/references/api-algorithm-optimization-strategies.md
  revision: aprof-1.1.0-pre-governance:sha256:27255603c8155ac2f34ba59420190390ba76d940bd9723790a6e72bb1defa5ad
  lines:
  - 6
  - 20
  sha256: sha256:27255603c8155ac2f34ba59420190390ba76d940bd9723790a6e72bb1defa5ad
  excerpt_sha256: sha256:f0d165b72d242a805fbc00e3903f2bb48703ad626737a2fc55d39d2e6ffc6332
learning:
  weight: 3
tags: []
seed_reason: 3 分：“向量化逐元素热循环”直接消除“标量逐元素热循环”对应的重复或不均衡工作，前提由动作独立核验。
relation: mitigated_by
from: problem.scalar_control_hot_loop
to: action.vectorize_scalar_loop
conditions: []
---

# problem.scalar_control_hot_loop → action.vectorize_scalar_loop

关系为 mitigated_by，专家排序初值为 3。3 分：“向量化逐元素热循环”直接消除“标量逐元素热循环”对应的重复或不均衡工作，前提由动作独立核验。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
