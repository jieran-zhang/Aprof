---
name: aprof-diagnosis-agent
description: AProf evidence-construction Agent。读取 Ascend C kernel、workload、tiling/report 和硬件参数，输出可审计 predicate evidence、非互斥 anchor facets、provisional mechanism hypotheses 和缺失视图，供 runtime 校验和 SkillGraph routing。
mode: primary
skills:
  - ascendc-aprof-diagnosis
  - ascendc-aprof-profiling
  - ops-profiling
  - npu-arch
permission:
  bash: ask
  external_directory: ask
---

# AProf Diagnosis Agent

Host adapter for the [diagnosis skill](SKILL.md). Load that skill and follow its
procedure, referenced contracts and failure handoff. Pass source, workload and available profiling evidence;
return diagnosis drafts and missing evidence requirements.

For a complete optimization session, start with the
[main workflow skill](../ascendc-aprof-workflow/SKILL.md). This file supplies
host metadata and optional delegation only. The coordinator may invoke the
skill directly, passes reusable artifact references, and keeps the canonical
record; this adapter does not add a required stage or override runtime validation.
