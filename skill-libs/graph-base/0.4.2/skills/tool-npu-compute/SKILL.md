---
name: tool-npu-compute
description: Collect and interpret npu-compute operator reports for AProf on supported Ascend 950 systems, or inspect existing .npu-rep, Section CSV, summary.jsonl, HardwareInfo.jsonl and PipeTrace.json evidence. Use after architecture-aware profiling selection or for an explicit npu-compute report request.
license: CANN-2.0
---

# npu-compute for AProf

Use npu-compute as the preferred mechanism profiler **where supported**. The
verified upstream tool supports Ascend 950 / dav-3510 Ascend C kernels; it does
not support 910C/A3. On A3, use [ops-profiling](../ops-profiling/SKILL.md) and
msprof. A tool-capability check does not establish that the current hardware or
CANN release is compatible. See [compatibility and provenance](NOTICE.md).

For collection, read [collection.md](references/collection.md). Preserve the
target program's argv and working directory, confirm installed Set/Section
support, and require both successful exit and actual report/import artifacts.
Continue already-authorized profiling without asking for the same permission.
Keep the system CANN and driver unchanged; a missing or incompatible tool is a
reported capability limit, not permission to upgrade the machine.

For analysis, read [evidence.md](references/evidence.md). Keep raw files and
collection identities intact; missing values remain unknown. Select Sections
from the diagnostic hypothesis, and explain measured differences separately
from their possible cause. A schema-valid report or a successful target program
alone does not establish valid collection or optimization gain.

Use the release's [profiling skill](../ascendc-aprof-profiling/SKILL.md) for the
collector, normalization and formal gate handoff. It owns repeated measurement,
full correctness and source replay. This skill supplies tool-specific meaning;
it does not replace the timing protocol or decide candidate acceptance.

For a Pipeline report, run the bundled read-only inspector:

```bash
python3 scripts/inspect_pipe_trace.py <PipeTrace.json> --format json
```

The inspector validates the retained upstream trace format; formal metric
admission still belongs to the runtime. Read the sampling limits before using
its event counts or busy-time totals in a diagnosis.
