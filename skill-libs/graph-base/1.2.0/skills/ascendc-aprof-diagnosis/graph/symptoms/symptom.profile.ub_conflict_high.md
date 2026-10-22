---
schema_version: aprof.knowledge-record/v1
id: symptom.profile.ub_conflict_high
kind: symptom
version: 1.0.0
status: active
title: Vector 的 UB 冲突计数偏高
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
  - 69
  - 74
  sha256: sha256:9bf71febdfee0429bc107731ac339a59941e55f0aeed27cd0030a4cd1ec5aaa2
  excerpt_sha256: sha256:d97b8923cb1a6b09e0fc57872e11dced5b5c6f46bd6afbc63bb0689ddff75149
learning:
  gain: 1
tags: []
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
view: profile
evidence:
  rule: Vector 的 UB 冲突计数偏高；按来源中的源码/字段定义核验，不能从表面占比单独推断。
  fields:
  - vector_total_conflict_ratio
  - bank_conflict_ratio
  - bank_group_conflict_ratio
  units:
    vector_total_conflict_ratio: 按原报告单位；比值与容量分母须绑定平台
    bank_conflict_ratio: 按原报告单位；比值与容量分母须绑定平台
    bank_group_conflict_ratio: 按原报告单位；比值与容量分母须绑定平台
  extractor: unimplemented
  unknown_when: 缺少源码、原始计数、时间区间或对应平台分母；未实现 extractor 未经人工证据核验时。
  threshold_scope: 保留历史经验阈值的原平台与 shape 范围；不设通用阈值。
---

# Vector 的 UB 冲突计数偏高

这是 profile 渠道的一项可核验特征。记录原始证据位置、单位、平台、shape 与 evidence_id。

只有相应证据成立才填写 true；无法核验填写 unknown。false 必须是已检查后的不成立，不是字段缺失。旧 extractor 尚未实现，允许有来源引用的人工审读。

证据规则和原始字段见元数据；不把历史经验阈值跨平台直接套用。
