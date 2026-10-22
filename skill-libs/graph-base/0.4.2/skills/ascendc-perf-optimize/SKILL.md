---
name: ascendc-perf-optimize
description: Separate algorithm parallel planning from execution tuning in an AProf operator candidate, using workload evidence and the published SkillGraph route.
---

# AProf optimization boundaries

First use `ascendc-aprof-parallel-planning` to choose task decomposition, ownership, algorithm and reduction/workspace protocol. Then use `ascendc-aprof-optimization` to implement one execution change under the chosen plan and workload group.

Distinguish insufficient independent tasks from inefficient execution of sufficient tasks. Changing partition axes, split-K, merge trees or cross-core ownership creates a new parallel plan. Changing tile lengths, copy granularity, buffer depth, scheduling or an equivalent local API under the same ownership is execution tuning.

Read [execution mechanisms](references/execution-mechanisms.md) for single-core bounds and [algorithm families](../ascendc-tiling-design/references/algorithm-families.md) for decomposition choices. Neither document supplies performance evidence: use source, measured counters and paired timing from the actual target. Preserve the selected correctness/runtime-validated parent, its source lineage and rejected attempts across iterations. Record performance admission separately; an exploratory parent is not a production best.
