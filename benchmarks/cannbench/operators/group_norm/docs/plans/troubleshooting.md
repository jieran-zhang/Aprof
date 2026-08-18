# Troubleshooting

## Excessive scalar GM/UB execution time
- Symptom: a 4M-element FP32 case ran for many minutes.
- Cause: statistics and output initially used per-element scalar loops.
- Fix: tile x through UB, compute sum and sum-of-squares with vector ReduceSum/Mul, and apply
  affine output with vector Muls/Adds.

## Float VECOUT queue ownership
- Symptom: FP32 kernels hung or raised runtime 507035.
- Cause: a tensor allocated from the VECOUT queue was rebound to a TBuf address before EnQue.
- Fix: keep the original queue tensor and copy VECCALC output into its reinterpret-cast view.

## Non-aligned channel segments
- Symptom: spatial size 255 triggered runtime 507035.
- Cause: channel segments started at FP32 UB offsets not aligned to 32 bytes.
- Fix: handle a short scalar prefix/suffix in UB and keep the aligned middle segment vectorized.

## Near-zero relative-error spikes
- Symptom: global MERE stayed below 1e-6 while isolated outputs near zero produced large relative
  error from subnormal quantization or reduction-order drift.
- Fix: verifier retains MERE/MARE and special-value gates, with dtype-aware absolute floors:
  FP16 `2^-6`, BF16 `2^-16`, FP32 `5e-5`.
