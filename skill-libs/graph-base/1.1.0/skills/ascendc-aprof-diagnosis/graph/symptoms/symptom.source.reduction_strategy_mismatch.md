---
schema_version: aprof.knowledge-record/v1
id: symptom.source.reduction_strategy_mismatch
kind: symptom
version: 1.0.0
status: active
title: AR/ARA 分支未随 A/R 和容量调整
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
  - 92
  - 92
  sha256: sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  excerpt_sha256: sha256:85319e9fcd2232856dda05246f506a228641871b0760298bda87d9ba8b644699
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/tiling-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/tiling-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  lines:
  - 73
  - 73
  sha256: sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  excerpt_sha256: sha256:af8ee073d36877e56da3f4e1f339251d6c26dae5941d3eb2a8833c65e50e6606
learning:
  gain: 1
tags:
- tiling
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
view: source
evidence:
  rule: AR/ARA 分支未随 A/R 和容量调整
  fields:
  - 源码位置、shape 和 tiling
  units:
    raw: 原后端单位；时间区间和字节口径需记录
  extractor: unimplemented
  unknown_when: 对应源码、字段、区间、平台分母或工作量模型缺失时保持 unknown。
  threshold_scope: 来源中的经验阈值仅在原平台与 workload 成立；本轮没有校准通用阈值。
---

# AR/ARA 分支未随 A/R 和容量调整

AR/ARA 分支未随 A/R 和容量调整。

写入 evidence_id 与原始引用，区分事实、派生公式和推测。没有自动 extractor；人工标注必须保留可核验依据。相关字段和候选判别见来源片段，未观测到不等于 false。
