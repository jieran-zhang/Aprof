---
schema_version: aprof.knowledge-record/v1
id: action.batch_writeback
kind: action
version: 1.0.0
status: active
title: 合并连续有效输出写回
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/data-movement-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/data-movement-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:58e28c093db98279fc16b45d1140c4673e3f9b312392618908c515bdc58b04e3
  lines:
  - 68
  - 68
  sha256: sha256:58e28c093db98279fc16b45d1140c4673e3f9b312392618908c515bdc58b04e3
  excerpt_sha256: sha256:046dfba849eeb560f933ea7982af6157d5e2fe71d68cbcc073e24ffc9d82f602
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/data-movement-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/data-movement-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:58e28c093db98279fc16b45d1140c4673e3f9b312392618908c515bdc58b04e3
  lines:
  - 72
  - 72
  sha256: sha256:58e28c093db98279fc16b45d1140c4673e3f9b312392618908c515bdc58b04e3
  excerpt_sha256: sha256:d7df4d171f1e21d25af9e45446cab3a978a620720009c24f873e0245d1189de4
learning:
  bias: 0
tags:
- data_movement
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
transformation: 合并连续有效输出写回
preconditions:
- fact: symptom.source.fragmented_writeback
  state: true
- fact: constraint.output_ownership
  state: true
- fact: constraint.semantic_equivalence
  state: true
- fact: constraint.capacity
  state: true
invariants:
- 完整语义和精度
- 有效元素覆盖和唯一写回
- 容量、同步与所有权合法
expected_effect: 预期减少该机制的额外成本；具体方案由 C2 比较、C3 实施，统一计时核验。
---

# 合并连续有效输出写回

合并连续有效输出写回。

这是方向性变换，不规定 tile、核数、buffer 个数或上游硬件常数。C1 携带此内容和前提快照；C2 从规划知识树选择方案、容量公式和 fallback；C3 从执行知识树选择实现方法。
