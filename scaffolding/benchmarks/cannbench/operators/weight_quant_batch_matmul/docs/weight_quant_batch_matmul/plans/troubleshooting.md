# Troubleshooting

## 2026-08-12 — task path initially resolved below `benchmarks/`

- Symptom: generator raised `FileNotFoundError` before any device launch.
- Cause: `scripts/cases.py` used `parents[4]`, whose value is the `benchmarks` directory.
- Fix: resolve the repository root with `parents[5]`.
- Prevention: count the script/operator/operators/cannbench/benchmarks levels explicitly when linking authoritative task files.

## 2026-08-12 — direct AIV multi-block launch exposed only one physical block id

- Symptom: only indices congruent to 8 modulo 40 were dequantized, making case 1 fail badly.
- Cause: this standalone mixed AIC/AIV executable did not provide dense logical `GetBlockIdx()` values for the requested AIV block count on the active device.
- Fix: correctness-first AIV stages launch one block and traverse their complete tensors; Cube remains parallelized by `MatmulImpl`.
- Prevention: dump and compare the intermediate dequantized matrix before trusting end-to-end matmul errors.

## 2026-08-12 — FP16 cancellation outlier exceeded MARE despite tiny absolute error

- Symptom: case 6 had MERE `6.6e-6`, but one value near 0.002 differed by `8e-5`, making MARE 0.034.
- Cause: Cube and CPU reference FP32 reduction orders differ around strong cancellation.
- Fix: on device, recompute only Cube results with magnitude below 1 using compensated FP32 scalar accumulation before bias and output cast (dav-2201 AICore rejects FP64 operations).
- Prevention: inspect both absolute error and the actual worst-reference magnitude when only MARE fails.

The verifier applies the ecosystem small-value rule before MERE/MARE: errors no larger than `1e-3` (FP16) or `5e-3` (BF16) contribute zero relative error. This prevents a sub-ULP absolute difference around cancellation from being misclassified as a large relative error.
