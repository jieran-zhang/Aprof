---
schema_version: aprof.knowledge-record/v1
id: edge.action.register_spill
kind: edge
version: 1.0.0
status: active
title: problem.register_spill → action.shorten_scalar_lifetimes
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
  weight: 2
tags: []
seed_reason: 2 分：缩短对象存活期可能减少 spill，但实际寄存器分配由编译器决定，须重新核对报告。
relation: mitigated_by
from: problem.register_spill
to: action.shorten_scalar_lifetimes
conditions: []
---

# problem.register_spill → action.shorten_scalar_lifetimes

关系为 mitigated_by，专家排序初值为 2。2 分：缩短对象存活期可能减少 spill，但实际寄存器分配由编译器决定，须重新核对报告。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
