# Troubleshooting

## FP32 fused multiply-add contraction

- Symptom: initial case 2 had MERE `2.13e-7` but MARE `0.062` near zero.
- Cause: the device compiler contracted `acc + scale*term` while the golden materializes multiply
  and add as two FP32 operations.
- Fix: materialize the product through a volatile scalar before the ordered addition.
- Evidence: case 2 changed from millions of one-ULP differences to bitwise equality.
- Prevention: preserve reference rounding points explicitly in fused-composite scalar kernels.

No unresolved issues. Validation uses physical device 1 exclusively. The verifier computes the
golden in bounded row chunks so the 262144×512 case does not require duplicate full-size tensors.
