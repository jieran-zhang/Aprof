---
schema_version: aprof.knowledge-record/v1
id: edge.action.tail_slow_path
kind: edge
version: 1.0.0
status: active
title: problem.tail_slow_path → action.vectorize_tail
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/tiling-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/tiling-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  lines:
  - 88
  - 88
  sha256: sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  excerpt_sha256: sha256:1946b5dcbbe8891830ae578b4b6ad08f97b1cfa2439fb33d9b48c4d5fa87ed75
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/pipeline-parallel-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/pipeline-parallel-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:bced4edd582c450d50baacc8a22abd061d79b2c3fa956142cc7329356afec6f1
  lines:
  - 75
  - 75
  sha256: sha256:bced4edd582c450d50baacc8a22abd061d79b2c3fa956142cc7329356afec6f1
  excerpt_sha256: sha256:d1fb57e98d01b845fa43b0258b378b466a0823b16cfe2b0b72a85050baf3eb2a
learning:
  weight: 3
tags: []
seed_reason: 3 分：“让尾块使用有界向量路径”直接消除“尾块走低效独立慢路径”对应的重复或不均衡工作，前提由动作独立核验。
relation: mitigated_by
from: problem.tail_slow_path
to: action.vectorize_tail
conditions: []
---

# problem.tail_slow_path → action.vectorize_tail

关系为 mitigated_by，专家排序初值为 3。3 分：“让尾块使用有界向量路径”直接消除“尾块走低效独立慢路径”对应的重复或不均衡工作，前提由动作独立核验。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
