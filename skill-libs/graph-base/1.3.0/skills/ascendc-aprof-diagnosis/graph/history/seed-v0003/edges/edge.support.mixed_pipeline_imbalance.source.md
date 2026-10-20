---
schema_version: aprof.knowledge-record/v1
id: edge.support.mixed_pipeline_imbalance.source
kind: edge
version: 1.0.0
status: active
title: symptom.source.mixed_pipeline_imbalance → problem.mixed_pipeline_imbalance
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
seed_reason: 2 分：“AIC/AIV 阶段任务粒度或后处理比例不同”支持“混合计算阶段节拍失衡”；有明确关联，仍需排除邻近机制或工作量解释。
relation: supports
from: symptom.source.mixed_pipeline_imbalance
to: problem.mixed_pipeline_imbalance
conditions: []
---

# symptom.source.mixed_pipeline_imbalance → problem.mixed_pipeline_imbalance

关系为 supports，专家排序初值为 2。2 分：“AIC/AIV 阶段任务粒度或后处理比例不同”支持“混合计算阶段节拍失衡”；有明确关联，仍需排除邻近机制或工作量解释。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
