# Upstream Reference (ops-nn)

These files are copied from [cann/ops-nn](https://gitcode.com/cann/ops-nn) for traceability.
They are **not** compiled by the direct-invoke CMake target.

| File | Source |
|------|--------|
| `fast_gelu_apt.cpp` | `activation/fast_gelu/op_kernel/fast_gelu_apt.cpp` |
| `fast_gelu_dag.h` | `activation/fast_gelu/op_kernel/arch35/fast_gelu_dag.h` |

The runnable skeleton is `../fast_gelu_kernel.asc`, which implements the same formula without ATV OSS dependencies.
