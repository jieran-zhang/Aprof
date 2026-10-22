---
schema_version: aprof.knowledge-record/v1
id: symptom.profile.missing_kernel_fusion
kind: symptom
version: 1.0.0
status: active
title: 调用启动和中间流量相对有用计算明显
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
  - 71
  - 71
  sha256: sha256:9c1fc5b3c90ba93734ca1e2ff7e074b3091bd506ffdd457165e46f80fdb9a214
  excerpt_sha256: sha256:a1cea15d1d3fa3b8a706be803b66f004c54a5a736cd92a6881a9cfc6116e640b
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/api-algorithm-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/api-algorithm-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:9c1fc5b3c90ba93734ca1e2ff7e074b3091bd506ffdd457165e46f80fdb9a214
  lines:
  - 70
  - 70
  sha256: sha256:9c1fc5b3c90ba93734ca1e2ff7e074b3091bd506ffdd457165e46f80fdb9a214
  excerpt_sha256: sha256:a5f2ac5bc75340d70d168c6fe3a0ffd871225abe498cd727f25a2c9bc4ccc38d
learning:
  gain: 1
tags:
- api_algorithm
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
view: profile
evidence:
  rule: 调用启动和中间流量相对有用计算明显
  fields:
  - 'Task CSV: full kernel sequence'
  - read_main_memory_datas
  - write_main_memory_datas
  - 'source: producer/consumer chain'
  units:
    raw: 采用实际后端原单位；字段名为来源族，通配符和视图须映射实际版本字段
    derived: 比值与差值需注明分子分母、时间窗口、平台上限来源
  extractor: unimplemented
  unknown_when: 对应源码、字段、区间、平台分母或工作量模型缺失时保持 unknown。
  threshold_scope: 来源中的经验阈值仅在原平台与 workload 成立；本轮没有校准通用阈值。
---

# 调用启动和中间流量相对有用计算明显

调用启动和中间流量相对有用计算明显。

写入 evidence_id 与原始引用，区分事实、派生公式和推测。没有自动 extractor；人工标注必须保留可核验依据。相关字段和候选判别见来源片段，未观测到不等于 false。
