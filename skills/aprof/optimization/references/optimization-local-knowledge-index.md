# Local targeted knowledge index

Read only the reference that resolves the current uncertainty. These are AProf-owned distilled resources, available in both the checkout and generated plugin. Source links in NOTICE files are provenance, never runtime skill dependencies.

| Question | Local reference |
| --- | --- |
| Actual SoC/ISA, A2 vs A3, usable cores/memory, evidence confidence | [Platform evidence](../../support/npu-arch/references/platform-evidence.md) |
| RegBase, SIMT, new/removed CV paths, SDK feature requirements | [3510 execution constraints](../../support/npu-arch/references/regbase-simt.md) |
| Copy alignment/tail, buffer/event lifetime, repeat/mask, Cast/Reduce/MatMul/Sort boundaries | [API contracts](../../support/ascendc-api-best-practices/references/api-contracts.md) |
| MTE setup/bandwidth, scalar/vector hot loops, double buffers, memory residency or pipeline gaps | [Execution mechanisms](../../support/ascendc-perf-optimize/references/execution-mechanisms.md) |
| Norm/Reduction, Sort/TopK, MatMul/GMM, FA/Softmax decomposition | [Algorithm families](../../support/ascendc-tiling-design/references/algorithm-families.md) |
| Metadata conditions, tiling key, actual host/kernel dispatch and fallback | [Tiling dispatch](../../support/ascendc-tiling-design/references/tiling-dispatch.md) |

Record the requested path, actual content hash, purpose and candidate/plan when read. A reference supplies a mechanism or constraint; it never substitutes for source/workload/profiling evidence. If the exact API remains uncertain, inspect the installed SDK and version-matched official documentation using the local `ascendc-docs-search` guidance.
