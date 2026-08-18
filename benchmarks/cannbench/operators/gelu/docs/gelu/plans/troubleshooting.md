# Troubleshooting

## Tanh cancellation

- Symptom: direct `0.5*x*(1+tanh(...))` failed float32 case 8 because values
  near x=-5 became about -1.49e-7 while the PyTorch golden rounds to -0.
- Cause: cancellation in `1+tanh(y)` amplified the vector Tanh approximation.
- Fix: use the algebraically equivalent stable logistic evaluation and
  explicitly round its FP32 probability to PyTorch's 2^-23 vector grid.
- Prevention: prefer stable exponential/logistic forms for saturated tanh
  expressions when a strict relative-error metric includes values near zero.

## Exact-mode negative tail

- Symptom: BF16 case 9 passed MERE but failed MARE for x around -5 because
  `1+erf(x/sqrt(2))` lost precision.
- Cause: cancellation plus the Erf approximation's finite clipping range.
- Fix: evaluate the equivalent `0.5*x*erfc(-x/sqrt(2))` expression using the
  five-vector Erfc workspace and reproduce the FP32 zero-tail boundary.
- Prevention: use complementary error functions for Gaussian negative tails.
