---
schema_version: aprof.knowledge-record/v1
id: edge.action.mixed_pipeline_imbalance
kind: edge
version: 1.0.0
status: active
title: problem.mixed_pipeline_imbalance → action.rebalance_mixed_stages
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/pipeline-parallel-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/pipeline-parallel-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:bced4edd582c450d50baacc8a22abd061d79b2c3fa956142cc7329356afec6f1
  lines:
  - 72
  - 72
  sha256: sha256:bced4edd582c450d50baacc8a22abd061d79b2c3fa956142cc7329356afec6f1
  excerpt_sha256: sha256:f332ca0ab2465065bf17f622c0bc56d90a8517fd52ffb7fc22d514addec03297
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/pipeline-parallel-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/pipeline-parallel-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:bced4edd582c450d50baacc8a22abd061d79b2c3fa956142cc7329356afec6f1
  lines:
  - 69
  - 69
  sha256: sha256:bced4edd582c450d50baacc8a22abd061d79b2c3fa956142cc7329356afec6f1
  excerpt_sha256: sha256:9fb77b6c76c680eba3183e8e3f355bc17632e1fa4707242d412b712cc67fe6bd
learning:
  weight: 2
tags: []
seed_reason: 2 分：改变阶段任务量或配比可能缩短关键路径，也会增加同步和 workspace 成本。
relation: mitigated_by
from: problem.mixed_pipeline_imbalance
to: action.rebalance_mixed_stages
conditions: []
---

# problem.mixed_pipeline_imbalance → action.rebalance_mixed_stages

关系为 mitigated_by，专家排序初值为 2。2 分：改变阶段任务量或配比可能缩短关键路径，也会增加同步和 workspace 成本。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
