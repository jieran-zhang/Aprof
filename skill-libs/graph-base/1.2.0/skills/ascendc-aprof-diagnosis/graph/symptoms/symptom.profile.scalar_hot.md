---
schema_version: aprof.knowledge-record/v1
id: symptom.profile.scalar_hot
kind: symptom
version: 1.0.0
status: active
title: 有效工作区间 Scalar 时间占比高
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/diagnosis/references/api-algorithm-diagnosis-metrics.md
  original_path: skills/aprof/diagnosis/references/api-algorithm-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:9bf71febdfee0429bc107731ac339a59941e55f0aeed27cd0030a4cd1ec5aaa2
  lines:
  - 20
  - 27
  sha256: sha256:9bf71febdfee0429bc107731ac339a59941e55f0aeed27cd0030a4cd1ec5aaa2
  excerpt_sha256: sha256:5ec6c11909cb2414cbb1b84e85c09c41cbcbc71207791a5f8fddf5340c143040
learning:
  gain: 1
tags: []
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
view: profile
evidence:
  rule: 有效工作区间 Scalar 时间占比高；按来源中的源码/字段定义核验，不能从表面占比单独推断。
  fields:
  - scalar_ratio
  - scalar_time
  - icache_miss_rate
  units:
    scalar_ratio: 按原报告单位；比值与容量分母须绑定平台
    scalar_time: 按原报告单位；比值与容量分母须绑定平台
    icache_miss_rate: 按原报告单位；比值与容量分母须绑定平台
  extractor: unimplemented
  unknown_when: 缺少源码、原始计数、时间区间或对应平台分母；未实现 extractor 未经人工证据核验时。
  threshold_scope: 保留历史经验阈值的原平台与 shape 范围；不设通用阈值。
---

# 有效工作区间 Scalar 时间占比高

这是 profile 渠道的一项可核验特征。记录原始证据位置、单位、平台、shape 与 evidence_id。

只有相应证据成立才填写 true；无法核验填写 unknown。false 必须是已检查后的不成立，不是字段缺失。旧 extractor 尚未实现，允许有来源引用的人工审读。

证据规则和原始字段见元数据；不把历史经验阈值跨平台直接套用。
