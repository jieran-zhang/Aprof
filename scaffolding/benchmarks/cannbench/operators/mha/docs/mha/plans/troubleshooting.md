# Troubleshooting

## dav-2201 direct AIV block coverage

- Symptom: case 1 had mostly-zero reordered Q and MERE above 1.
- Cause: treating parent/subcore IDs as ordinary independent logical blocks in
  a multi-block direct AIV launch caused incomplete/racing scalar GM coverage.
- Fix: scalar reorder/scatter use a single AIC parent; AIV softmax uses one
  parent and explicit row ranges.
- Prevention: prove the first reordered buffer before debugging downstream
  QK/softmax/PV.

## Long single-parent softmax

- Symptom: BF16 case 2 was correct for early heads but later batches retained
  raw scores, producing max absolute errors around 0.5.
- Cause: one kernel invocation iterated too many rows.
- Fix: launch softmax in bounded `max(1,131072/Skv)` row chunks on one AIV
  parent and synchronize each chunk.
- Evidence: case 2 raw max error fell to one BF16 ULP.

## Near-zero relative-error spikes

- Symptom: FP16/BF16 raw MARE was large while raw max absolute error was at
  most one output ULP.
- Resolution: preserve raw metrics and apply only local one-ULP or
  `eps*sum(abs(weight*V))` forward-error equivalence. Special values remain
  strict; no global denominator floor is used.
