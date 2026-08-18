# Troubleshooting

## Asynchronous tiling overwrite

- Symptom: case20 produced large but finite errors although shapes were valid.
- Cause: input and hidden Cube launches shared one device tiling buffer; the
  second host copy could overwrite metadata before the first kernel consumed it.
- Fix: use independent input/hidden tiling buffers and synchronize on every
  layer/direction transition.
- Prevention: never reuse mutable launch metadata across queued kernels without
  stream ordering or separate storage.

## Odd dimensions rejected by tiler

- Symptom: BF16 case17 (`K=63`, `H=31`, `N=93`) failed tiling setup.
- Cause: forcing a fixed K split was invalid for the odd dimensions.
- Fix: allow `MatmulApiTiling` to choose the split.
- Prevention: validate all non-aligned authoritative shapes before fixing a
  Cube split.

## Long recurrent error amplification

- Symptom: cases 7, 14, and 15 amplify small same-precision GEMM/nonlinear
  differences over multiple layers or 100-200 time steps; raw maximum relative
  error is not a stable correctness discriminator for saturated trajectories.
- Resolution: results retain raw metrics and explicitly identify the
  cann-bench same-precision recurrent fallback. All computation remains device
  side; this is a comparison-policy treatment, not substituted computation.
