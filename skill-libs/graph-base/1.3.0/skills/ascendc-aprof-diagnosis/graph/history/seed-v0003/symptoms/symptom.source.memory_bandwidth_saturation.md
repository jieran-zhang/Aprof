---
schema_version: aprof.knowledge-record/v1
id: symptom.source.memory_bandwidth_saturation
kind: symptom
version: 1.0.0
status: active
title: 热路径以大块连续搬运为主
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/data-movement-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/data-movement-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:58e28c093db98279fc16b45d1140c4673e3f9b312392618908c515bdc58b04e3
  lines:
  - 71
  - 71
  sha256: sha256:58e28c093db98279fc16b45d1140c4673e3f9b312392618908c515bdc58b04e3
  excerpt_sha256: sha256:40cf97cdaaeea3eb3cc641c95cc06f85b78db33183b9bb819b0a9260c70159b8
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/bound-deep-routing.md
  original_path: skills/ascendc-aprof-diagnosis/references/bound-deep-routing.md
  revision: aprof-1.1.0-pre-governance:sha256:620c25b91946e0523ffc99aaddae20b8b6989d8b6a1474d7c15c49cb43bfbbbe
  lines:
  - 48
  - 48
  sha256: sha256:620c25b91946e0523ffc99aaddae20b8b6989d8b6a1474d7c15c49cb43bfbbbe
  excerpt_sha256: sha256:33c702652aa6f9cbbc51464f7c3f1818dbc4f5e623cfe6835bd3267de4b5407c
learning:
  gain: 1
tags:
- data_movement
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
view: source
evidence:
  rule: 热路径以大块连续搬运为主；只排查小粒度形态，不能独立证明带宽饱和。
  fields:
  - 源码位置、shape 和 tiling
  units:
    raw: 原后端单位；时间区间和字节口径需记录
  extractor: unimplemented
  unknown_when: 对应源码、字段、区间、平台分母或工作量模型缺失时保持 unknown。
  threshold_scope: 来源中的经验阈值仅在原平台与 workload 成立；本轮没有校准通用阈值。
---

# 热路径以大块连续搬运为主

热路径以大块连续搬运为主。

写入 evidence_id 与原始引用，区分事实、派生公式和推测。没有自动 extractor；人工标注必须保留可核验依据。相关字段和候选判别见来源片段，未观测到不等于 false。
