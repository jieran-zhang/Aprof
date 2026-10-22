---
schema_version: aprof.knowledge-record/v1
id: symptom.profile.redundant_cast
kind: symptom
version: 1.0.0
status: active
title: Cast 指令占用明显且不承担必要精度边界
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/api-algorithm-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/api-algorithm-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:9c1fc5b3c90ba93734ca1e2ff7e074b3091bd506ffdd457165e46f80fdb9a214
  lines:
  - 65
  - 65
  sha256: sha256:9c1fc5b3c90ba93734ca1e2ff7e074b3091bd506ffdd457165e46f80fdb9a214
  excerpt_sha256: sha256:fc6046ab557edc2427920fd72df3a792b7640585fc670416312cc9c0948147c9
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/bound-deep-routing.md
  original_path: skills/ascendc-aprof-diagnosis/references/bound-deep-routing.md
  revision: aprof-1.1.0-pre-governance:sha256:620c25b91946e0523ffc99aaddae20b8b6989d8b6a1474d7c15c49cb43bfbbbe
  lines:
  - 61
  - 61
  sha256: sha256:620c25b91946e0523ffc99aaddae20b8b6989d8b6a1474d7c15c49cb43bfbbbe
  excerpt_sha256: sha256:7a330c74b26bff1596853d8e04a44dfeaf9e8a9fa3e8ff1249e143fb7f406b37
learning:
  gain: 1
tags:
- api_algorithm
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
view: profile
evidence:
  rule: Cast 指令占用明显且不承担必要精度边界
  fields:
  - 'trace: Cast instruction intervals'
  - 'ArithmeticUtilization.csv: dtype-specific vector work'
  units:
    raw: 采用实际后端原单位；字段名为来源族，通配符和视图须映射实际版本字段
    derived: 比值与差值需注明分子分母、时间窗口、平台上限来源
  extractor: unimplemented
  unknown_when: 对应源码、字段、区间、平台分母或工作量模型缺失时保持 unknown。
  threshold_scope: 来源中的经验阈值仅在原平台与 workload 成立；本轮没有校准通用阈值。
---

# Cast 指令占用明显且不承担必要精度边界

Cast 指令占用明显且不承担必要精度边界。

写入 evidence_id 与原始引用，区分事实、派生公式和推测。没有自动 extractor；人工标注必须保留可核验依据。相关字段和候选判别见来源片段，未观测到不等于 false。
