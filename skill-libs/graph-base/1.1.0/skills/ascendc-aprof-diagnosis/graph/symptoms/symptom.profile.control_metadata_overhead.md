---
schema_version: aprof.knowledge-record/v1
id: symptom.profile.control_metadata_overhead
kind: symptom
version: 1.0.0
status: active
title: Scalar 窗口与控制指令重复且工作量足以摊薄启动
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
  - 33
  - 33
  sha256: sha256:620c25b91946e0523ffc99aaddae20b8b6989d8b6a1474d7c15c49cb43bfbbbe
  excerpt_sha256: sha256:e3fee122fde5b0c1cc133b6c2423df3118f018c3a989704461d8541a91f8c403
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/bound-deep-routing.md
  original_path: skills/ascendc-aprof-diagnosis/references/bound-deep-routing.md
  revision: aprof-1.1.0-pre-governance:sha256:620c25b91946e0523ffc99aaddae20b8b6989d8b6a1474d7c15c49cb43bfbbbe
  lines:
  - 34
  - 34
  sha256: sha256:620c25b91946e0523ffc99aaddae20b8b6989d8b6a1474d7c15c49cb43bfbbbe
  excerpt_sha256: sha256:aba4d9e8aad40479336071b1a316b5e76ee068235a8d00468b9163bb00035121
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/api-algorithm-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/api-algorithm-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:9c1fc5b3c90ba93734ca1e2ff7e074b3091bd506ffdd457165e46f80fdb9a214
  lines:
  - 123
  - 123
  sha256: sha256:9c1fc5b3c90ba93734ca1e2ff7e074b3091bd506ffdd457165e46f80fdb9a214
  excerpt_sha256: sha256:01a42765a9b26cce6d4684b214832a6fc39feab8ef30b3bfdf08887ff86a6ee1
learning:
  gain: 1
tags:
- api_algorithm
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
view: profile
evidence:
  rule: Scalar 窗口与控制指令重复且工作量足以摊薄启动
  fields:
  - ai*_scalar_ratio
  - 'trace: mask/branch/index intervals'
  - 'source: TilingData'
  units:
    raw: 采用实际后端原单位；字段名为来源族，通配符和视图须映射实际版本字段
    derived: 比值与差值需注明分子分母、时间窗口、平台上限来源
  extractor: unimplemented
  unknown_when: 对应源码、字段、区间、平台分母或工作量模型缺失时保持 unknown。
  threshold_scope: 来源中的经验阈值仅在原平台与 workload 成立；本轮没有校准通用阈值。
---

# Scalar 窗口与控制指令重复且工作量足以摊薄启动

Scalar 窗口与控制指令重复且工作量足以摊薄启动。

写入 evidence_id 与原始引用，区分事实、派生公式和推测。没有自动 extractor；人工标注必须保留可核验依据。相关字段和候选判别见来源片段，未观测到不等于 false。
