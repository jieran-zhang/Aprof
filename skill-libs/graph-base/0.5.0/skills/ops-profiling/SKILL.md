---
name: ops-profiling
description: Route AProf hardware collection to npu-compute on supported Ascend 950 systems or msprof on 910C/A3, and preserve original reports for runtime source replay.
---

# AProf hardware collectors

After build and full correctness, select the supported backend with
[ascendc-aprof-profiling](../ascendc-aprof-profiling/SKILL.md).
Use npu-compute as the preferred mechanism profiler on a verified compatible
950/dav-3510 environment. The current 910C/A3 route uses `msprof op`; verified
npu-compute documentation does not include A3. Other architectures require an
explicit capability check. Keep the system CANN and driver unchanged.

Use the release's [collector interface](../ascendc-aprof-profiling/references/collector-interface.md)
for independent captures and normalized source evidence. For npu-compute file
semantics, load [tool-npu-compute](../tool-npu-compute/SKILL.md).

The bundled msprof tools remain available for additional views and old reports:

```bash
bash scripts/msprof_profile_run.sh --help
bash scripts/msprof_profile_run.sh --warm-up=10 --output=<unique-dir> -- <binary> <args>
python3 scripts/msprof_perf_summary.py <PROF_GROUP-dir> <archive-dir>
python3 scripts/perf_summary.py <OPPROF-dir> <archive-dir>
```

Resolve these paths from the installed skill directory. The inherited
`--compare`/`--batch` modes are compatibility utilities; use the AProf correctness
and paired-timing protocols for candidate admission. Mechanism profiling uses
independent captures, while production gain uses at least thirty alternating
AB/BA timing-only pairs and the runtime's confidence/stability checks.

Preserve raw CSV/JSONL/trace, exact commands, source/binary/workload hashes,
collection/kernel identity, hardware and dispatch key. Missing fields stay
unknown. A human summary is not a candidate verdict or attested policy reward.
