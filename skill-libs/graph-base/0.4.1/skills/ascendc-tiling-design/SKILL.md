---
name: ascendc-tiling-design
description: Design capacity-safe workload dispatch and per-core tiling after an AProf parallel plan, including direct-launch tiling-key plumbing.
---

# AProf tiling and dispatch

Read [tiling and dispatch](references/tiling-dispatch.md). Host metadata selects an algorithm/workload group and a uint64 tiling key; the key must select an actual kernel implementation. Capacity queries, dynamic shape support and a general fallback remain part of the operator.

Use `ascendc-aprof-parallel-planning` before changing the task decomposition, reduction or ownership. Within a selected plan, derive UB/L1/L0 occupancy from every live tensor, queue depth, alignment, scratch and workspace slot. Use runtime AIC/AIV counts and usable memory; never substitute a model-name constant.

For MatMul, Norm/Reduction, Sort/TopK and attention, read [algorithm families](references/algorithm-families.md). Precision thresholds and semantics come from the operator's declared reference/checker; no external precision-standard skill is needed.
