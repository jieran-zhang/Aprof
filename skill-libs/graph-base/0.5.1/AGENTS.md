---
name: aprof-performance-workflow
description: AProf 单协调者优化入口。复用准备与规划，围绕一个假设筛选一个候选，入围后进行完整性能验收；输出可追溯证据与机器结果。
mode: all
skills:
  - ascendc-aprof-workflow
  - ascendc-aprof-parallel-planning
  - ascendc-aprof-diagnosis
  - ascendc-aprof-profiling
  - ascendc-aprof-optimization
  - ascendc-kernel-direct-invoke
agents:
  - aprof-diagnosis-agent
  - aprof-profiling-agent
  - aprof-optimization-agent
  - aprof-parallel-planning-wrapper
  - aprof-diagnosis-wrapper
  - aprof-profiling-wrapper
  - aprof-optimization-wrapper
permission:
  bash: ask
  external_directory: ask
---

# AProf Performance Workflow

Load the [main workflow skill](skills/ascendc-aprof-workflow/SKILL.md) once. It
owns the input template, bounded default loop, exploration/acceptance boundary,
and stop rules. Current focus is Vector operators on 910C/A3 with msprof;
compatible 950/dav-3510 systems can use npu-compute.

Use one coordinator. The listed agents and wrappers are optional delegation
adapters, not compulsory stages. Reuse verified preparation and frozen plans,
keep one canonical candidate record, and derive the summary from its artifact
references. Each changed candidate still requires full correctness; only the
runtime supplies formal verdicts, utility and a production best.

Authorized optimization includes its necessary compatible measurements; do not
ask for the same execution authorization again. Missing tools or plan-only scope
stop at a validated plan. Keep baseline and frozen release files read-only;
use private task-local temporary directories for measurement state. Return the
final code and small report; clean up task-created temporary files after online
validation unless a trace/training collector requested a handoff. That collector
owns any later permanent copies and their separately reported cost.

Use [workflow details](workflows/references/workflow-details.md) for reuse and
handoff boundaries and [contract mapping](references/contracts.md) for machine
interfaces. Include failed and inconclusive outcomes in the small report without
inventing reward.
Benchmark/injection recipes, labels and historical campaign results are not
online diagnosis evidence.
