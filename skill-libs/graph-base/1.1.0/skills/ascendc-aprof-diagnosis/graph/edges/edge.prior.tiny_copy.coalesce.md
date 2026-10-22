---
schema_version: aprof.knowledge-record/v1
id: edge.prior.tiny_copy.coalesce
kind: edge
version: 1.0.0
status: active
title: problem.tiny_transfer_setup_amplification → action.coalesce_contiguous_transfers
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/optimization/references/data-movement-optimization-strategies.md
  original_path: skills/aprof/optimization/references/data-movement-optimization-strategies.md
  revision: aprof-1.1.0-pre-governance:sha256:5c3a68ff44e8f93f33ca3d6492c5b1894224e66b382e2e59fcb842b7e1086479
  lines:
  - 6
  - 24
  sha256: sha256:5c3a68ff44e8f93f33ca3d6492c5b1894224e66b382e2e59fcb842b7e1086479
  excerpt_sha256: sha256:8f073cd2b7e2f255e96848dc5b876750f574be250c786a30bd2d737c0212847b
learning:
  weight: 3
tags: []
seed_reason: 3 分：“合并连续小搬运”直接消除“小搬运放大发射开销”对应的重复或不均衡工作，前提由动作独立核验。
relation: mitigated_by
from: problem.tiny_transfer_setup_amplification
to: action.coalesce_contiguous_transfers
conditions: []
---

# problem.tiny_transfer_setup_amplification → action.coalesce_contiguous_transfers

关系为 mitigated_by，专家排序初值为 3。3 分：“合并连续小搬运”直接消除“小搬运放大发射开销”对应的重复或不均衡工作，前提由动作独立核验。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
