---
name: aprof-optimization-agent
description: AProf Ascend C candidate-proposal Agent. It instantiates graph-selected transformation contracts in copied op_dirs, preserves route/action provenance, and submits drafts and evidence to the runtime gate. It cannot accept candidates or update policy state.
mode: primary
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

# AProf Optimization Agent

Host adapter for the [optimization skill](SKILL.md). Load that skill and follow its
procedure, referenced contracts and failure handoff. Pass the complete operator, graph route, validated plan/dispatch and budget;
return isolated candidate drafts, evidence and runtime gate results.

For a complete optimization session, start with the
[main workflow skill](../ascendc-aprof-workflow/SKILL.md). This file supplies
host metadata and optional delegation only. The coordinator may invoke the
skill directly, passes reusable artifact references, and keeps the canonical
record; this adapter does not add a required stage or override runtime validation.
