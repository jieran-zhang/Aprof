---
schema_version: aprof.knowledge-record/v1
id: symptom.source.ub_live_bytes_near_capacity
kind: symptom
version: 1.0.0
status: active
title: 对齐后同时存活的片上 buffer 接近可用容量
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/optimization/references/onchip-memory-optimization-strategies.md
  original_path: skills/aprof/optimization/references/onchip-memory-optimization-strategies.md
  revision: aprof-1.1.0-pre-governance:sha256:e7f4c274e3b3dbf51286c3131d382225cec631480111322fc8beca9b0a6f5de0
  lines:
  - 18
  - 25
  sha256: sha256:e7f4c274e3b3dbf51286c3131d382225cec631480111322fc8beca9b0a6f5de0
  excerpt_sha256: sha256:8abc1eef34edbec8cd585d7655042acc44c7bf0628565843223ea1d9ef0b5e25
learning:
  gain: 1
tags: []
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
view: source
evidence:
  rule: 对齐后同时存活的片上 buffer 接近可用容量；按来源中的源码/字段定义核验，不能从表面占比单独推断。
  fields:
  - buffer_lifetimes
  - ub_capacity_bytes
  - alignment_bytes
  units:
    buffer_lifetimes: 按原报告单位；比值与容量分母须绑定平台
    ub_capacity_bytes: 按原报告单位；比值与容量分母须绑定平台
    alignment_bytes: 按原报告单位；比值与容量分母须绑定平台
  extractor: unimplemented
  unknown_when: 缺少源码、原始计数、时间区间或对应平台分母；未实现 extractor 未经人工证据核验时。
  threshold_scope: 保留历史经验阈值的原平台与 shape 范围；不设通用阈值。
---

# 对齐后同时存活的片上 buffer 接近可用容量

这是 source 渠道的一项可核验特征。记录原始证据位置、单位、平台、shape 与 evidence_id。

只有相应证据成立才填写 true；无法核验填写 unknown。false 必须是已检查后的不成立，不是字段缺失。旧 extractor 尚未实现，允许有来源引用的人工审读。

证据规则和原始字段见元数据；不把历史经验阈值跨平台直接套用。
