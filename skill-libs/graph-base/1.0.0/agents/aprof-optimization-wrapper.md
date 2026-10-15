---
name: aprof-optimization-wrapper
description: AProf workflow 内部优化 wrapper。负责规范化 evidence 与 graph route，调用 optimization skill 生成隔离 candidate draft，并把 draft/evidence 交给机器 gate；不自行裁决候选。
mode: subagent
skills:
  - ascendc-aprof-optimization
  - ascendc-aprof-diagnosis
  - ascendc-aprof-profiling
  - ops-profiling
  - ops-simulator
  - npu-arch
permission:
  bash: ask
  external_directory: ask
---

# AProf Optimization Wrapper

Use the [main optimization entry](../skills/ascendc-aprof-workflow/SKILL.md)
for session orchestration. This adapter is optional; the coordinator may invoke
the skill directly and retains the canonical record. Invoke the
[optimization skill](../skills/ascendc-aprof-optimization/SKILL.md)
with the complete operator, graph route, validated plan/dispatch and budget; return isolated candidate drafts, evidence and runtime gate results.

Pass the selected release/graph, source identities, constraints and evidence
references unchanged. Follow the invoked skill's input/output contracts, required
references and failure handoff. This adapter defines no separate procedure,
measurement policy or candidate verdict; machine validation remains authoritative.
