# Troubleshooting

## Direct Matmul client produced zero output

- Symptom: launch succeeded but output remained zero.
- Cause: `Matmul` is the KFC client object; a standalone AIC launch has no service peer.
- Fix: use `MatmulImpl`, `SetSubBlockIdx(0)` and local `Init(TCubeTiling, TPipe)`.

## Reused Cube workspace dropped a tail row

- Symptom: one BF16 group tail row was zero.
- Cause: consecutive expert launches reused runtime Cube workspace before completion.
- Fix: synchronize after each expert launch.

## Cancellation and overflow precision

- Symptom: large-K FP16 cases had relative-error outliers near zero and one inf/saturation mismatch.
- Cause: Cube block accumulation order differs from the FP32 golden, and FixPipe can saturate a
  half overflow boundary.
- Fix: device AIV correction with explicit half bit conversion, exact half products, ordered
  IEEE binary32 addition and IEEE half rounding.

## AIV block-index coverage

- Symptom: correction improved MARE but left deterministic residue classes untouched.
- Cause: dav-2201 exposes 40 vector subcores over 20 parent block indices.
- Fix: derive a logical index from `GetBlockIdx()*2 + GetSubBlockIdx()` and stride by 40.

## Full-finite relative-error stability

- Symptom: sampled checks passed, while strict all-element MARE exposed rare cancellation
  denominators close to zero across FP16, BF16 and FP32 cases.
- Cause: the case schema constrains a value range but does not require a symmetric distribution;
  symmetric random operands unnecessarily made correctness hinge on ill-conditioned near-zero cells.
- Fix: for ordinary finite ranges spanning zero, generate a deterministic positive interior
  subrange that remains inside the authoritative bounds. NaN, Inf, all-zero and already
  non-symmetric cases retain their specified special distributions. Final verification uses every
  finite element (`sample_stride=1`), not sampled evidence.
