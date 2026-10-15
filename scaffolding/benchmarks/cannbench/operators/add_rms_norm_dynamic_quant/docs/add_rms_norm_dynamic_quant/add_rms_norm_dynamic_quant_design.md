# AddRmsNormDynamicQuant flash design

## Device computation

Rows are distributed across available vector cores. Each core processes its
rows serially in 2048-element tiles. A row uses three device-side passes:

1. cast x1/x2 to FP32, add, write dtype-cast `xOut`, square and reduce tiles;
2. calculate refined FP32 reciprocal RMS, reconstruct normalized/gamma-scaled
   values and reduce their absolute maximum;
3. reconstruct the values and use `AscendQuant<float>` for saturating int8
   conversion with round-to-nearest-even behavior.

No normalized tensor, statistic, scale, or quantized value is computed on the
host. Re-reading inputs avoids a large GM temporary and preserves the golden's
FP32 residual sum rather than normalizing the dtype-rounded xOut.

## UB budget

At tile size 2048, four raw input/output buffers consume at most 4 KiB each,
the int8 output consumes 2 KiB, four FP32 work/reduction buffers consume 8 KiB
each, and scalar reduction buffers consume under 0.1 KiB. Total live UB is
below 51 KiB. Buffers are reused between passes. All GM transfers use padded
extended copies so prime tails are supported.

## Accuracy choices

The residual, square accumulation, normalization and gamma multiplication are
FP32. `Rsqrt` receives two Newton refinements. BF16 output uses `CAST_ROUND`;
FP16 uses the validated native conversion. Dynamic quantization permits at
most one int8 code difference, matching the established task harness policy;
FP32 scale and xOut are checked with the task precision metric.
