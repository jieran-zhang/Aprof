# Troubleshooting

Record non-trivial build, runtime, and precision failures here during NPU
validation.

## Invalid host-side Unique implementation

- Symptom: the first version used C++ containers to compute sorted unique
  values and inverse IDs before launching a copy kernel.
- Cause: dynamic-output handling was incorrectly treated as permission to
  perform operator semantics on the host.
- Fix: removed all host set/sort/map code and replaced it with NPU-side key
  encoding, radix sorting, compaction, and inverse mapping kernels.
- Prevention: host code may schedule kernels and read a device-produced shape,
  but must never derive semantic outputs.

The replacement NPU radix implementation passed all 20 cases. Its largest
case produced a 2 GiB int64 inverse tensor entirely from device kernels.
