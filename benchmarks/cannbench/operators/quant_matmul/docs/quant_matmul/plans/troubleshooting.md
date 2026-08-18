# Troubleshooting

## AIV direct-launch block indexing left most output elements unwritten

- Symptom: initial case 18 had MERE 0.96185, MARE 1.0, and only 625 of 16384
  output elements were nonzero.
- Cause: treating the reported vector subcore count as a dense set of direct
  kernel block indices and using that value as the scalar loop stride. On
  dav-2201, the direct AIV parent/subcore mapping did not match that assumption.
- Fix: launch the correctness-only postprocess with one AIV block and stride
  one. Case 18 then became bitwise equal, followed by all remaining cases.
- Prevention: prove direct-launch block-index coverage on a sentinel buffer
  before using reported vector-core counts as logical strides.
