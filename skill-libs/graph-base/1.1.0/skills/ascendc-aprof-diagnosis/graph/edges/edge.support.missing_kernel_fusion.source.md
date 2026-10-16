---
schema_version: aprof.knowledge-record/v1
id: edge.support.missing_kernel_fusion.source
kind: edge
version: 1.0.0
status: active
title: symptom.source.missing_kernel_fusion → problem.missing_kernel_fusion
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
  weight: 2
tags: []
seed_reason: 2 分：“连续可组合子操作通过 GM 中间张量连接”支持“跨 kernel 融合不足”；有明确关联，仍需排除邻近机制或工作量解释。
relation: supports
from: symptom.source.missing_kernel_fusion
to: problem.missing_kernel_fusion
conditions: []
---

# symptom.source.missing_kernel_fusion → problem.missing_kernel_fusion

关系为 supports，专家排序初值为 2。2 分：“连续可组合子操作通过 GM 中间张量连接”支持“跨 kernel 融合不足”；有明确关联，仍需排除邻近机制或工作量解释。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
