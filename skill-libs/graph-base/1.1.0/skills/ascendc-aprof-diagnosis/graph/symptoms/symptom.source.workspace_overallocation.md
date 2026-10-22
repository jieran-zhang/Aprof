---
schema_version: aprof.knowledge-record/v1
id: symptom.source.workspace_overallocation
kind: symptom
version: 1.0.0
status: active
title: 按最大 shape 或过量槽位分配 workspace
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/onchip-memory-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/onchip-memory-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:8d9fb7fb09995999b68b59bb166ce51eb6d3cb9e7f5240dc2cf7d5156d7361e1
  lines:
  - 69
  - 69
  sha256: sha256:8d9fb7fb09995999b68b59bb166ce51eb6d3cb9e7f5240dc2cf7d5156d7361e1
  excerpt_sha256: sha256:a7e65beed2193c19504543679c2b38bb8ea86d53ec3dac4c375e33e2da8c7715
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/onchip-memory-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/onchip-memory-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:8d9fb7fb09995999b68b59bb166ce51eb6d3cb9e7f5240dc2cf7d5156d7361e1
  lines:
  - 70
  - 70
  sha256: sha256:8d9fb7fb09995999b68b59bb166ce51eb6d3cb9e7f5240dc2cf7d5156d7361e1
  excerpt_sha256: sha256:076752ee0df51ce93370eb1489b75db0478be214d766a391f69e9870a48817a6
learning:
  gain: 1
tags:
- onchip_memory
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
view: source
evidence:
  rule: 按最大 shape 或过量槽位分配 workspace
  fields:
  - 源码位置、shape 和 tiling
  units:
    raw: 原后端单位；时间区间和字节口径需记录
  extractor: unimplemented
  unknown_when: 对应源码、字段、区间、平台分母或工作量模型缺失时保持 unknown。
  threshold_scope: 来源中的经验阈值仅在原平台与 workload 成立；本轮没有校准通用阈值。
---

# 按最大 shape 或过量槽位分配 workspace

按最大 shape 或过量槽位分配 workspace。

写入 evidence_id 与原始引用，区分事实、派生公式和推测。没有自动 extractor；人工标注必须保留可核验依据。相关字段和候选判别见来源片段，未观测到不等于 false。
