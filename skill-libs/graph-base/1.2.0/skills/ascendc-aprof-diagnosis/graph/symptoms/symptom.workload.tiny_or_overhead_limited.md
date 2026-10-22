---
schema_version: aprof.knowledge-record/v1
id: symptom.workload.tiny_or_overhead_limited
kind: symptom
version: 1.0.0
status: active
title: 工作量不足以摊薄固定启动开销
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/diagnosis/references/workload-aware-diagnosis.md
  original_path: skills/aprof/diagnosis/references/workload-aware-diagnosis.md
  revision: aprof-1.1.0-pre-governance:sha256:2a5bf97bf325f7ef04b93279c42c18a8a34e9471d2d71f30a2584b2b1f6a6113
  lines:
  - 18
  - 23
  sha256: sha256:2a5bf97bf325f7ef04b93279c42c18a8a34e9471d2d71f30a2584b2b1f6a6113
  excerpt_sha256: sha256:e0a044dca17d424d8b9cbec8e598b2dad025a60b2ae38e03a20ec1415a5ff00b
learning:
  gain: 1
tags: []
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
view: workload
evidence:
  rule: 工作量不足以摊薄固定启动开销；按来源中的源码/字段定义核验，不能从表面占比单独推断。
  fields:
  - element_count
  - effective_elements_per_core
  - attainable_utilization
  units:
    element_count: 按原报告单位；比值与容量分母须绑定平台
    effective_elements_per_core: 按原报告单位；比值与容量分母须绑定平台
    attainable_utilization: 按原报告单位；比值与容量分母须绑定平台
  extractor: unimplemented
  unknown_when: 缺少源码、原始计数、时间区间或对应平台分母；未实现 extractor 未经人工证据核验时。
  threshold_scope: 保留历史经验阈值的原平台与 shape 范围；不设通用阈值。
---

# 工作量不足以摊薄固定启动开销

这是 workload 渠道的一项可核验特征。记录原始证据位置、单位、平台、shape 与 evidence_id。

只有相应证据成立才填写 true；无法核验填写 unknown。false 必须是已检查后的不成立，不是字段缺失。旧 extractor 尚未实现，允许有来源引用的人工审读。

证据规则和原始字段见元数据；不把历史经验阈值跨平台直接套用。
