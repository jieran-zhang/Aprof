# Troubleshooting

## Float scale GM write

- Symptom: case 1 int8 output was bit-exact, but scattered rows of the scale output remained zero.
- Root cause: a four-byte scalar GM store (both naked pointer and `GlobalTensor::SetValue` forms) was not reliably committed for every row in this mixed vector/scalar kernel.
- Fix: stage the scale in a 32-byte UB tensor and use a four-byte `DataCopyPad` GM transfer.
- Prevention: use UB staging plus `DataCopyPad` for sub-32-byte scalar float output writes.
