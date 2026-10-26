---
schema_version: aprof.knowledge-record/v1
id: problem.ub_bank_conflict
kind: problem
version: 1.0.0
status: active
title: UB 布局引起 bank 冲突
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/diagnosis/references/bound-deep-routing.md
  original_path: skills/aprof/diagnosis/references/bound-deep-routing.md
  revision: aprof-1.1.0-pre-governance:sha256:7b5f46925a304a3d6db77c905675c8ecae3d12eeedeac501743bdc07f932d44e
  lines:
  - 58
  - 64
  sha256: sha256:7b5f46925a304a3d6db77c905675c8ecae3d12eeedeac501743bdc07f932d44e
  excerpt_sha256: sha256:8e89ada79f00c47215a93a0214ab24ee0e350adcc21bccb8cb2f914aa98750db
learning:
  bias: 0
tags:
- api_algorithm
- onchip_memory
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
mechanism: UB 布局引起 bank 冲突
alternatives:
- 工作负载限制
- 其他流水或搬运机制
---

# UB 布局引起 bank 冲突

UB 布局引起 bank 冲突。先核验关联症状及反证，再提出本轮可检验假设。问题族只作为标签，不能代替机制。容量超限和同步错误应先作为正确性约束排查。
