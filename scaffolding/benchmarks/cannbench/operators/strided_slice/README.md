# StridedSlice Ascend C direct-invoke benchmark

Correctness-first implementation for the 20 cases in
`third_party/cann-bench/tasks/level3/strided_slice`.

```bash
./run.sh --case 1 --device 0
./run.sh --all --device 0
```

The runner generates deterministic inputs, builds a direct ACL/Ascend C executable,
runs the kernel on a real NPU, and checks the output bit-for-bit against the source
offsets defined by the task golden semantics. Performance profiling is intentionally
not collected in the Flash development pass.
