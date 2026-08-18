# Troubleshooting

## [Phase 7.1] Native FP16 torch reference has cancellation defect

**现象：** Case 2 passed average relative error but native-FP16 torch comparison reported MARE about 9 at a near-zero output.

**根因：** At filter index 11576, native `torch.nn.grad.conv3d_weight` returns `-0.0131226`, while the direct device contraction returns about `0.1053`. Independent FP64 summation is `0.105187` and the same torch operation on explicitly FP32 inputs is `0.104788`. A scalar device correction also returned `0.10535`; forcing the kernel toward the native FP16 value would make it mathematically wrong.

**解决方案：** Keep original inputs unchanged. Gate correctness against explicit FP32 contraction followed by one output cast, with a fixed per-dtype `2^-5` small-value floor and local one-output-ULP equivalence. Preserve native-dtype MERE/MARE, exactness and special-value agreement in every case result as diagnostics.

**经验：** Low-precision CPU convolution backends are not always reliable mathematical contraction oracles in cancellation regions.

**预防：** For contraction tasks, audit a failing point with FP64 direct summation and explicit-FP32 torch before changing a correct device kernel.

## [Phase 7.2] BF16 cancellation and padded Inf contamination

**现象：** Case 5 had one low-amplitude BF16 cancellation outlier; case 13 produced extra NaNs around padded coordinates because Cube multiplied materialized zero padding by Inf.

**根因：** Cube and the FP32 CPU oracle use different legal reduction trees. For special values, explicit im2col zero padding is not semantically equivalent to omitting an out-of-range term because IEEE `0*Inf` is NaN.

**解决方案：** The BF16 device post kernel recomputes non-zero accumulators with magnitude below 1 and all non-finite accumulators by iterating only valid source coordinates. All other outputs retain the Cube contraction. The final verifier uniformly applies the per-output `2*gamma_K*sum_abs_products` rule; only 511 output elements across all 20 cases require it, and maximum accepted `device-oracle/bound` is `2.3377506295219064e-05`.

**经验：** Materialized convolution padding needs explicit special-value handling, and contraction-order differences need a local theoretical error bound rather than a global tolerance.

**预防：** Include Inf padding and high-dynamic cancellation cases before declaring a Cube contraction complete.

## [Phase 6.1] Scalar filter-gradient kernel is computationally infeasible

**现象：** Output-parallel scalar reduction would require tens to hundreds of billions of multiply-adds for the large original cases.

**根因：** The reduction dimension is `N*Do*Ho*Wo` and must be repeated for every filter element.

**解决方案：** Express each grouped kernel-offset contraction as device `grad^T * im2col(x)` and execute it with `AscendC::MatmulImpl` Cube.

**经验：** L3 contraction tasks require a Cube formulation before implementation.

**预防：** Estimate total contraction operations and workspace sizes during specification analysis.
