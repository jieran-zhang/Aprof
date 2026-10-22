---
schema_version: aprof.knowledge-record/v1
id: symptom.profile.tasks_below_available_cores
kind: symptom
version: 1.0.0
status: active
title: 有效任务数少于可用核数
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/diagnosis/references/ai-core-utilization-diagnosis-metrics.md
  original_path: skills/aprof/diagnosis/references/ai-core-utilization-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:0a70b21924e9ba29d6a75280699009b1f46afd4e9bd0fd3eb9880d592105e475
  lines:
  - 20
  - 28
  sha256: sha256:0a70b21924e9ba29d6a75280699009b1f46afd4e9bd0fd3eb9880d592105e475
  excerpt_sha256: sha256:a3eb83c9d7033f7d03bb10827f2f2c369815bffebcf3880bb1437fd2fa90f48d
learning:
  gain: 1
tags: []
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
view: profile
evidence:
  rule: 有效任务数少于可用核数；按来源中的源码/字段定义核验，不能从表面占比单独推断。
  fields:
  - total_tasks
  - available_cores
  - block_dim
  units:
    total_tasks: 按原报告单位；比值与容量分母须绑定平台
    available_cores: 按原报告单位；比值与容量分母须绑定平台
    block_dim: 按原报告单位；比值与容量分母须绑定平台
  extractor: unimplemented
  unknown_when: 缺少源码、原始计数、时间区间或对应平台分母；未实现 extractor 未经人工证据核验时。
  threshold_scope: 保留历史经验阈值的原平台与 shape 范围；不设通用阈值。
---

# 有效任务数少于可用核数

这是 profile 渠道的一项可核验特征。记录原始证据位置、单位、平台、shape 与 evidence_id。

只有相应证据成立才填写 true；无法核验填写 unknown。false 必须是已检查后的不成立，不是字段缺失。旧 extractor 尚未实现，允许有来源引用的人工审读。

证据规则和原始字段见元数据；不把历史经验阈值跨平台直接套用。
