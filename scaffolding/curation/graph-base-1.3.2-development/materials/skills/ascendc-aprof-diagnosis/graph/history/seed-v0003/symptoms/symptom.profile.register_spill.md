---
schema_version: aprof.knowledge-record/v1
id: symptom.profile.register_spill
kind: symptom
version: 1.0.0
status: active
title: 编译报告或指令跟踪确认非算法必要的 spill/LoadStore
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/bound-deep-routing.md
  original_path: skills/ascendc-aprof-diagnosis/references/bound-deep-routing.md
  revision: aprof-1.1.0-pre-governance:sha256:620c25b91946e0523ffc99aaddae20b8b6989d8b6a1474d7c15c49cb43bfbbbe
  lines:
  - 36
  - 36
  sha256: sha256:620c25b91946e0523ffc99aaddae20b8b6989d8b6a1474d7c15c49cb43bfbbbe
  excerpt_sha256: sha256:7d686e034229907a1aa618783bf9a57377656b6b26806363f1a39ae44b8422d2
learning:
  gain: 1
tags:
- api_algorithm
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
view: profile
evidence:
  rule: 编译报告或指令跟踪确认非算法必要的 spill/LoadStore
  fields:
  - 'compiler: spill/stack report'
  - 'trace: scalar LoadStore instructions'
  units:
    raw: 采用实际后端原单位；字段名为来源族，通配符和视图须映射实际版本字段
    derived: 比值与差值需注明分子分母、时间窗口、平台上限来源
  extractor: unimplemented
  unknown_when: 对应源码、字段、区间、平台分母或工作量模型缺失时保持 unknown。
  threshold_scope: 来源中的经验阈值仅在原平台与 workload 成立；本轮没有校准通用阈值。
---

# 编译报告或指令跟踪确认非算法必要的 spill/LoadStore

编译报告或指令跟踪确认非算法必要的 spill/LoadStore。

写入 evidence_id 与原始引用，区分事实、派生公式和推测。没有自动 extractor；人工标注必须保留可核验依据。相关字段和候选判别见来源片段，未观测到不等于 false。
