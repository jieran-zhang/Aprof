# Collection and report identity

The pinned upstream documentation supports Ascend 950 (dav-3510), Ascend C
`__cube__`, `__vector__` and `__mix__` kernels, with a single operator invoked
once through `<<<>>>` or aclnn. Do not profile an arbitrary multi-operator runner
as though it met that contract. Match the installed tool to its CANN release;
master's installation instructions do not promise standalone upgrades.

For current-environment execution, record the installed executable/version and
query its capabilities before choosing the command:

```bash
npu-compute --help
npu-compute --list-sets
npu-compute --list-sections
```

These queries do not run the target. Set and Section names are case sensitive.
The pinned skill documents the following sets; installed output is authoritative:

| Set | Sections, in order |
| --- | --- |
| `basic` | Pipeline, PipeUtilization, Memory, MemoryL0, MemoryUB, L2Cache, ArithmeticUtilization |
| `full` | All basic Sections, then ResourceConflictRatio |

Use individual `--section` options for a focused question. With a Set plus extra
Sections, expansion follows command-line order and deduplicates on first
appearance. `basic` plus `ResourceConflictRatio` is therefore the documented
`full` selection. Choose only the views needed by the AProf hypotheses.

Native examples, from the target's working directory:

```bash
npu-compute --section PipeUtilization --section Memory -- ./operator <arguments>
npu-compute --set full --export <new-report.npu-rep> -- ./operator <arguments>
npu-compute --import <existing-report.npu-rep> --export <existing-export-parent>
```

`--` ends tool-option parsing; every following argument belongs to the target.
Use an interpreter for a non-executable script. Do not wrap build, data
generation, verification or another npu-compute invocation in the target.

Collection succeeds only when exit status is zero, stdout publishes
`npu-compute: report= <path>`, and that `.npu-rep` exists. Import succeeds only
when exit status is zero, stdout publishes `npu-compute: unpacked= <directory>`,
and the directory contains recognizable results. Use these actual paths.
`--export` during import names a parent; the tool creates a unique child.
Do not guess that child's name or overwrite an earlier report.

Keep root results and each `collection-p...` result separate. Identify a kernel
using its own summary's `OpInfoSummary`, not a neighboring result or a directory
name inferred from msprof conventions. Missing kernel identity or ambiguous
multiple results block formal normalization until explicitly resolved.

For AProf collection use the installed
[collector interface](../../ascendc-aprof-profiling/references/collector-interface.md).
Its capture manifest binds raw report files, workload, source, device and
measurement policy. Internal replay, PMU rows and sampled Pipeline groups are
not independent repeats. The native npu-compute examples above are exploratory
unless the AProf repeated-capture and correctness requirements also hold.
