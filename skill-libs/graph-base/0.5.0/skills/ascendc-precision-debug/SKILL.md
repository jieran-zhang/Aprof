---
name: ascendc-precision-debug
description: Diagnose a failed AProf correctness gate while preserving the reference contract and recording the first divergent stage.
---

# AProf precision failure

Freeze the failing candidate and exact case/seed, selected tiling key, dtype/layout, reference hash, tolerances and command. Reproduce the first failure before tuning. Compare error coordinates with tile/core/tail boundaries and reduction axes; include signed/unsigned, NaN/Inf, zero, extreme magnitude and non-aligned cases allowed by the input contract.

Read [API and memory contracts](../ascendc-api-best-practices/references/api-contracts.md). Verify valid lengths, index stride units, output coverage, initialization, reduction accumulation dtype, Cast rounding and API support in the target SDK. For fused or multi-pass code, bisect intermediate stages with small diagnostic outputs or the SDK-supported DumpTensor mechanism. Debug outputs are not performance evidence; remove instrumentation before final measurement.

Use the operator's original reference/checker as the accuracy authority. Do not loosen tolerances, drop difficult cases or alter the reference to make an optimization pass. Changing reduction order or switching Norm algorithms requires a new parallel plan and full correctness verification. Preserve a typed accuracy failure and link the repair as a new attempt.
