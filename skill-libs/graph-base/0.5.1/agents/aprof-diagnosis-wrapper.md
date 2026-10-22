---
name: aprof-diagnosis-wrapper
description: AProf workflow 内部诊断 wrapper。负责把 workflow 输入规范化后交给 aprof-diagnosis-agent。
mode: subagent
skills:
  - ascendc-aprof-diagnosis
  - ops-profiling
  - npu-arch
permission:
  bash: ask
  external_directory: ask
---

# AProf Diagnosis Wrapper

Use the [main optimization entry](../skills/ascendc-aprof-workflow/SKILL.md)
for session orchestration. This adapter is optional; the coordinator may invoke
the skill directly and retains the canonical record. Invoke the
[diagnosis skill](../skills/ascendc-aprof-diagnosis/SKILL.md)
with source, workload and available profiling evidence; return diagnosis drafts and missing evidence requirements.

Pass the selected release/graph, source identities, constraints and evidence
references unchanged. Follow the invoked skill's input/output contracts, required
references and failure handoff. This adapter defines no separate procedure,
measurement policy or candidate verdict; machine validation remains authoritative.
