---
name: aprof-profiling-agent
description: AProf Profiling Agent。接收 evidence requirements，生成带 warmup/repeat 的采集计划，按架构执行或导入 npu-compute/msprof/simulator artifacts，并提交带 hash 的解析 draft 给 runtime 计算稳定 metric evidence。
mode: primary
skills:
  - ascendc-aprof-profiling
  - ascendc-kernel-direct-invoke
  - ops-profiling
  - npu-arch
permission:
  bash: ask
  external_directory: ask
---

# AProf Profiling Agent

Host adapter for the [profiling skill](SKILL.md). Load that skill and follow its
procedure, referenced contracts and failure handoff. Pass requested metrics, operator commands, correctness contract and execution authority;
return profiling/parsing drafts and immutable execution evidence.

For a complete optimization session, start with the
[main workflow skill](../ascendc-aprof-workflow/SKILL.md). This file supplies
host metadata and optional delegation only. The coordinator may invoke the
skill directly, passes reusable artifact references, and keeps the canonical
record; this adapter does not add a required stage or override runtime validation.
