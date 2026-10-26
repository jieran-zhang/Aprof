---
schema_version: aprof.knowledge-record/v1
id: symptom.profile.steady_overlap
kind: symptom
version: 1.0.0
status: active
title: 时间线上存在稳定的搬运计算重叠
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
  - 51
  - 51
  sha256: sha256:620c25b91946e0523ffc99aaddae20b8b6989d8b6a1474d7c15c49cb43bfbbbe
  excerpt_sha256: sha256:331f86446b51f0a01e94aa03f7a1c1ad4171450ad5025d79ef7805815f2c5851
learning:
  gain: 1
tags: []
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
view: profile
evidence:
  rule: 稳态多 tile 区间存在持续 MTE/Compute 重叠
  fields:
  - trace/timeline
  units:
    timeline: 原始时间单位及稳态区间
  extractor: unimplemented
  unknown_when: 没有 timeline 或不能区分 prolog/steady/drain。
  threshold_scope: 同一任务、case、实现的稳态窗口。
---

# 时间线上存在稳定的搬运计算重叠

这是已观测的反证特征。未提供 timeline 时不能自动设为 true 或 false。
