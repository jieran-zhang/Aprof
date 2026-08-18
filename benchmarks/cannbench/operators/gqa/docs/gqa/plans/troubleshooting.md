# Troubleshooting

## Direct AIV scalar GM coverage

- Symptom: sparse zeros/fractional PV values although Cube launches succeeded.
- Cause: distributing scalar GM GetValue/SetValue loops by direct-launch block
  index did not provide reliable complete coverage on the two-vector-subcore
  dav-2201 execution model.
- Fix: perform layout conversion/scatter on one device block; dense QK/PV
  remains on Cube and softmax remains vectorized.
- Prevention: validate layout kernels first with zero Q/K and all-one V, where
  every output must be exactly one.

## Causal SLEEF range

- Symptom: all-NaN output after introducing the CPU-compatible exp polynomial.
- Cause: the polynomial exponent reconstruction is not valid for the causal
  mask sentinel near negative float max.
- Fix: causal rows use AscendC `Exp`; unmasked FP16 rows use the SLEEF-compatible
  polynomial. Explicit NaN/Inf counts were checked after the change.

## Scale rounding

- Symptom: structurally correct output differed by one FP16 ULP.
- Cause: Torch keeps the scaled score in input dtype, while the first device
  version multiplied the half score in FP32 without a dtype round trip.
- Fix: cast the scaled score back to input dtype and then to FP32 before mask
  and softmax.
