---
name: ascendc-performance-best-practices
description: Interpret AProf execution bottlenecks and choose evidence-backed copy, pipeline, buffer, vector, or cube changes within a frozen parallel plan.
---

# AProf execution practices

Read [execution mechanisms](../ascendc-perf-optimize/references/execution-mechanisms.md) for copy/pipeline/vector/scalar/buffer tuning, or [algorithm families](../ascendc-tiling-design/references/algorithm-families.md) when evidence points to decomposition. Use `npu-arch` to check architecture capabilities and `ascendc-aprof-optimization` to propose the candidate.

A high utilization counter does not prove a bottleneck, and tiny-workload idle cores do not prove poor implementation. Compare measured work, bytes and pipeline dependencies with the attainable workload bound. Changes to the global algorithm belong to parallel planning; an execution candidate keeps its plan hash fixed.
