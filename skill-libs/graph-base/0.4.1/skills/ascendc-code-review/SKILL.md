---
name: ascendc-code-review
description: Review an isolated AProf candidate for plan consistency, dispatch coverage, memory bounds, precision and synchronization before its build gate.
---

# AProf candidate static review

Compare the candidate with its declared parallel plan, dispatch plan and parent source. Check output ownership, coverage and overlap for every partition, exact reduction/tie/NaN rules, dynamic shapes, tails and integer arithmetic overflow. Metadata predicates must be mutually exclusive or explicitly rejected as ambiguous, and preserve a correct general fallback. Case IDs, reference outputs and tensor values cannot select a benchmark specialization.

Read the [bundled API contract reference](../ascendc-api-best-practices/references/api-contracts.md) for every changed overload or pipeline lifetime. Compute simultaneous UB/L1/L0/workspace occupancy including queue depth and scratch. Check every valid transfer length against allocation and stride units; a padded local buffer does not authorize a padded GM read/write. Check producers, waiters and consumers for each event and cross-core synchronization; verify no cycle or asymmetric path.

On 3510 use [RegBase and SIMT checks](../npu-arch/references/regbase-simt.md); avoid enabling unsupported APIs by a marketing model name. Return concrete file/line findings and evidence, or an explicit checked scope. The runtime gate determines acceptance; static review is one input.
