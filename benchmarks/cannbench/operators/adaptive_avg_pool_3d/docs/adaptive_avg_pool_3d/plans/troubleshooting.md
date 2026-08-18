# Troubleshooting

Record non-trivial build, runtime, and precision failures here during NPU
validation.

## AICore unsigned-to-float cast rejection

- Symptom: BiSheng rejected conversion of the unsigned 64-bit window volume
  directly to float.
- Cause: dav-2201 AICore scalar code does not permit that conversion form.
- Fix: narrow the bounded window volume to signed `int32_t`, then convert it
  to float for division.
- Prevention: use signed scalar dimensions for floating-point conversion in
  device helpers.
