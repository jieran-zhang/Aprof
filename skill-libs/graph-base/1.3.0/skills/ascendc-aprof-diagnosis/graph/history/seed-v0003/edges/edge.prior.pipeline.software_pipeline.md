---
schema_version: aprof.knowledge-record/v1
id: edge.prior.pipeline.software_pipeline
kind: edge
version: 1.0.0
status: active
title: problem.pipeline_serialization → action.software_pipeline_stages
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/optimization/references/pipeline-parallel-optimization-strategies.md
  original_path: skills/aprof/optimization/references/pipeline-parallel-optimization-strategies.md
  revision: aprof-1.1.0-pre-governance:sha256:106abe2ae5d0fde1eebe08e995949c674b633584eb1277b828382a132863c50c
  lines:
  - 8
  - 30
  sha256: sha256:106abe2ae5d0fde1eebe08e995949c674b633584eb1277b828382a132863c50c
  excerpt_sha256: sha256:daf6651306577b22b161bfb7352d2b4c6af4d90931616d7d61ade9ab01ba7c81
learning:
  weight: 2
tags: []
seed_reason: 2 分：重排允许独立搬运与计算重叠，但增加 buffer、事件和 prolog/drain 成本。
relation: mitigated_by
from: problem.pipeline_serialization
to: action.software_pipeline_stages
conditions: []
---

# problem.pipeline_serialization → action.software_pipeline_stages

关系为 mitigated_by，专家排序初值为 2。2 分：重排允许独立搬运与计算重叠，但增加 buffer、事件和 prolog/drain 成本。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
