---
schema_version: aprof.knowledge-record/v1
id: symptom.profile.transfer_compute_contention
kind: symptom
version: 1.0.0
status: active
title: Vector-MTE 冲突和 wait 与重叠窗口相关
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
  gain: 1
tags:
- pipeline_parallel
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
view: profile
evidence:
  rule: Vector-MTE 冲突和 wait 与重叠窗口相关
  fields:
  - 'ResourceConflictRatio.csv: aiv_vec_mte_cflt_ratio'
  - 'trace: concurrent intervals'
  units:
    raw: 采用实际后端原单位；字段名为来源族，通配符和视图须映射实际版本字段
    derived: 比值与差值需注明分子分母、时间窗口、平台上限来源
  extractor: unimplemented
  unknown_when: 对应源码、字段、区间、平台分母或工作量模型缺失时保持 unknown。
  threshold_scope: 来源中的经验阈值仅在原平台与 workload 成立；本轮没有校准通用阈值。
---

# Vector-MTE 冲突和 wait 与重叠窗口相关

Vector-MTE 冲突和 wait 与重叠窗口相关。

写入 evidence_id 与原始引用，区分事实、派生公式和推测。没有自动 extractor；人工标注必须保留可核验依据。相关字段和候选判别见来源片段，未观测到不等于 false。
