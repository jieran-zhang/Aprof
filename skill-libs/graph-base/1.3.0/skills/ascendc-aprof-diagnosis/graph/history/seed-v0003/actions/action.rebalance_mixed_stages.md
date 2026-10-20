---
schema_version: aprof.knowledge-record/v1
id: action.rebalance_mixed_stages
kind: action
version: 1.0.0
status: active
title: 平衡混合流水阶段工作量
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/pipeline-parallel-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/pipeline-parallel-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:bced4edd582c450d50baacc8a22abd061d79b2c3fa956142cc7329356afec6f1
  lines:
  - 72
  - 72
  sha256: sha256:bced4edd582c450d50baacc8a22abd061d79b2c3fa956142cc7329356afec6f1
  excerpt_sha256: sha256:f332ca0ab2465065bf17f622c0bc56d90a8517fd52ffb7fc22d514addec03297
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/pipeline-parallel-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/pipeline-parallel-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:bced4edd582c450d50baacc8a22abd061d79b2c3fa956142cc7329356afec6f1
  lines:
  - 69
  - 69
  sha256: sha256:bced4edd582c450d50baacc8a22abd061d79b2c3fa956142cc7329356afec6f1
  excerpt_sha256: sha256:9fb77b6c76c680eba3183e8e3f355bc17632e1fa4707242d412b712cc67fe6bd
learning:
  bias: 0
tags:
- pipeline_parallel
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
transformation: 平衡混合流水阶段工作量
preconditions:
- fact: symptom.source.mixed_pipeline_imbalance
  state: true
- fact: constraint.cross_engine_dependencies
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

# 平衡混合流水阶段工作量

平衡混合流水阶段工作量。

这是方向性变换，不规定 tile、核数、buffer 个数或上游硬件常数。C1 携带此内容和前提快照；C2 从规划知识树选择方案、容量公式和 fallback；C3 从执行知识树选择实现方法。
