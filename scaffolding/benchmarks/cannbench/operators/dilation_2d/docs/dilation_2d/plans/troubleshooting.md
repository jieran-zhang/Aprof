# Troubleshooting

## Scalar FP16 arithmetic rejected by compiler

- Symptom: Bisheng rejected `half + half` in an AICore scalar function.
- Fix: widen FP16 operands to float32 in device helpers, add, and convert back with explicit
  round-to-nearest-even bit conversion before maximum selection.
- Prevention: dav-2201 scalar kernels must not rely on native scalar half arithmetic.

## Visible-device remapping rejected the physical device index

- Symptom: with `ASCEND_RT_VISIBLE_DEVICES=1`, launching the harness with `--device 1`
  failed at `aclrtSetDevice` with error 107001.
- Fix: keep physical device 1 as the only visible device and pass its process-local ACL
  index, `--device 0`.
- Prevention: after constraining `ASCEND_RT_VISIBLE_DEVICES`, use the logical device index
  within the visible set; do not reuse the physical index in `aclrtSetDevice`.
