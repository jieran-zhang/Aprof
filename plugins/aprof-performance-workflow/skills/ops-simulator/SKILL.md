---
name: ops-simulator
description: Inspect Ascend simulator traces and instruction/pipeline gaps with bundled tools, preserving proxy status and target-specific capability limits.
---

# AProf simulator evidence

Confirm the configured target and installed `cannsim` or `msprof op simulator` command-line support. Run a small correctness-checked input with a bounded timeout and preserve the exact simulator version, command and trace. Simulator metrics are instruction/pipeline proxies, not hardware latency or production speedups.

For an existing Chrome trace use the local analyzer:

```bash
python3 scripts/trace_bubble_analyzer.py <trace-or-directory> --json -o <report.json>
```

Inspect gaps together with source dependencies and distinguish warmup/drain from steady state. Use [execution mechanisms](../ascendc-perf-optimize/references/execution-mechanisms.md) for copy/event/buffer bottlenecks; use [RegBase and SIMT](../npu-arch/references/regbase-simt.md) only after a supported architecture and SDK are established. These references absorb the former simulator's external regbase/direct-invoke dependencies. A trace cannot supply missing hardware counters or validate an API absent from the target SDK.
