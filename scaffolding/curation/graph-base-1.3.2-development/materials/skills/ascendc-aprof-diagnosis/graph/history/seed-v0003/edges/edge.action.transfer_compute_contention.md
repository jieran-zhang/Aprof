---
schema_version: aprof.knowledge-record/v1
id: edge.action.transfer_compute_contention
kind: edge
version: 1.0.0
status: active
title: problem.transfer_compute_contention → action.stagger_resource_access
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
  - 71
  - 71
  sha256: sha256:bced4edd582c450d50baacc8a22abd061d79b2c3fa956142cc7329356afec6f1
  excerpt_sha256: sha256:99b43c20006a11c2df3df1b50030607bc5a8d9c80a730f2fc3b329a4f38e0e0f
learning:
  weight: 2
tags: []
seed_reason: 2 分：错开访问可能降低资源冲突，也可能损失原有重叠，需比较两者成本。
relation: mitigated_by
from: problem.transfer_compute_contention
to: action.stagger_resource_access
conditions: []
---

# problem.transfer_compute_contention → action.stagger_resource_access

关系为 mitigated_by，专家排序初值为 2。2 分：错开访问可能降低资源冲突，也可能损失原有重叠，需比较两者成本。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
