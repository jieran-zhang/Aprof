---
name: aprof-parallel-planning-wrapper
description: Construct architecture-aware AProf algorithm/task plans and workload dispatch before concrete execution optimization.
mode: subagent
skills:
  - ascendc-aprof-parallel-planning
  - npu-arch
---

# AProf Parallel Planning Wrapper

Use the [main optimization entry](../skills/ascendc-aprof-workflow/SKILL.md)
for session orchestration. This adapter is optional; the coordinator may invoke
the skill directly and retains the canonical record. Invoke the
[parallel-planning skill](../skills/ascendc-aprof-parallel-planning/SKILL.md)
with the operator semantics, workload, architecture evidence and budget; return architecture, parallel-plan and dispatch drafts for runtime validation.

Pass the selected release/graph, source identities, constraints and evidence
references unchanged. Follow the invoked skill's input/output contracts, required
references and failure handoff. This adapter defines no separate procedure,
measurement policy or candidate verdict; machine validation remains authoritative.
