---
schema_version: aprof.knowledge-record/v1
id: symptom.source.ub_stride_conflict_risk
kind: symptom
version: 1.0.0
status: active
title: UB 起址或 stride 存在周期性冲突风险
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
  gain: 1
tags: []
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
view: source
evidence:
  rule: UB 起址或 stride 存在周期性冲突风险；按来源中的源码/字段定义核验，不能从表面占比单独推断。
  fields:
  - ub_offsets
  - block_strides
  - operand_layout
  - hardware_bank_geometry
  units:
    ub_offsets: 按原报告单位；比值与容量分母须绑定平台
    block_strides: 按原报告单位；比值与容量分母须绑定平台
    operand_layout: 按原报告单位；比值与容量分母须绑定平台
    hardware_bank_geometry: 按原报告单位；比值与容量分母须绑定平台
  extractor: unimplemented
  unknown_when: 缺少源码、原始计数、时间区间或对应平台分母；未实现 extractor 未经人工证据核验时。
  threshold_scope: 保留历史经验阈值的原平台与 shape 范围；不设通用阈值。
---

# UB 起址或 stride 存在周期性冲突风险

这是 source 渠道的一项可核验特征。记录原始证据位置、单位、平台、shape 与 evidence_id。

只有相应证据成立才填写 true；无法核验填写 unknown。false 必须是已检查后的不成立，不是字段缺失。旧 extractor 尚未实现，允许有来源引用的人工审读。

证据规则和原始字段见元数据；不把历史经验阈值跨平台直接套用。
