---
schema_version: aprof.knowledge-record/v1
id: edge.support.conflict.source
kind: edge
version: 1.0.0
status: active
title: symptom.source.ub_stride_conflict_risk → problem.ub_bank_conflict
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
  - 27
  - 32
  sha256: sha256:ef273a362b02e6e2409ca55e684d55d5f54cf539529acb9154319b996090dd1c
  excerpt_sha256: sha256:7754b4a7717efa2eea08cad77ec1ecab5a5c96736871d7fd98c7782a5c121bc1
learning:
  weight: 1
tags: []
seed_reason: 1 分：“UB 起址或 stride 存在周期性冲突风险”支持“UB 布局引起 bank 冲突”；源码形态只提供低特异性线索。
relation: supports
from: symptom.source.ub_stride_conflict_risk
to: problem.ub_bank_conflict
conditions: []
---

# symptom.source.ub_stride_conflict_risk → problem.ub_bank_conflict

关系为 supports，专家排序初值为 1。1 分：“UB 起址或 stride 存在周期性冲突风险”支持“UB 布局引起 bank 冲突”；源码形态只提供低特异性线索。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
