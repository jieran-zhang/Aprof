---
schema_version: aprof.knowledge-record/v1
id: edge.support.tail_slow_path.profile
kind: edge
version: 1.0.0
status: active
title: symptom.profile.tail_slow_path → problem.tail_slow_path
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
  weight: 2
tags: []
seed_reason: 2 分：“尾 shape 相对对齐 shape 明显恶化且定位到尾路径”支持“尾块走低效独立慢路径”；有明确关联，仍需排除邻近机制或工作量解释。
relation: supports
from: symptom.profile.tail_slow_path
to: problem.tail_slow_path
conditions: []
---

# symptom.profile.tail_slow_path → problem.tail_slow_path

关系为 supports，专家排序初值为 2。2 分：“尾 shape 相对对齐 shape 明显恶化且定位到尾路径”支持“尾块走低效独立慢路径”；有明确关联，仍需排除邻近机制或工作量解释。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
