---
schema_version: aprof.knowledge-record/v1
id: symptom.profile.mte_setup_dominated
kind: symptom
version: 1.0.0
status: active
title: MTE 占比高且单位指令有效搬运小、带宽低
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/diagnosis/references/bound-deep-routing.md
  original_path: skills/aprof/diagnosis/references/bound-deep-routing.md
  revision: aprof-1.1.0-pre-governance:sha256:7b5f46925a304a3d6db77c905675c8ecae3d12eeedeac501743bdc07f932d44e
  lines:
  - 42
  - 51
  sha256: sha256:7b5f46925a304a3d6db77c905675c8ecae3d12eeedeac501743bdc07f932d44e
  excerpt_sha256: sha256:e7416836e2c7c426cade861de5dc1046368fc3d93f8956fe1971fca631c2cdee
learning:
  gain: 1
tags: []
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
view: profile
evidence:
  rule: MTE 占比高且单位指令有效搬运小、带宽低；按来源中的源码/字段定义核验，不能从表面占比单独推断。
  fields:
  - mte2_ratio
  - memory_bandwidth_utilization
  - useful_bytes_per_mte_instruction
  units:
    mte2_ratio: 按原报告单位；比值与容量分母须绑定平台
    memory_bandwidth_utilization: 按原报告单位；比值与容量分母须绑定平台
    useful_bytes_per_mte_instruction: 按原报告单位；比值与容量分母须绑定平台
  extractor: unimplemented
  unknown_when: 缺少源码、原始计数、时间区间或对应平台分母；未实现 extractor 未经人工证据核验时。
  threshold_scope: 保留历史经验阈值的原平台与 shape 范围；不设通用阈值。
---

# MTE 占比高且单位指令有效搬运小、带宽低

这是 profile 渠道的一项可核验特征。记录原始证据位置、单位、平台、shape 与 evidence_id。

只有相应证据成立才填写 true；无法核验填写 unknown。false 必须是已检查后的不成立，不是字段缺失。旧 extractor 尚未实现，允许有来源引用的人工审读。

证据规则和原始字段见元数据；不把历史经验阈值跨平台直接套用。
