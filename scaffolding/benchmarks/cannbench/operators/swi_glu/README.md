# SwiGLU Ascend C direct invocation

Standalone Ascend910 (`dav-2201`) direct-invocation implementation of:

`output = silu(x0) * x1`, where `x0, x1 = input.chunk(2, dim)`.

It supports the official float16, float32, and bfloat16 cases and arbitrary
valid split dimensions. Build and run all official cases on NPU device 2:

```bash
./run.sh --all --device 2
```

Run one case without rebuilding:

```bash
./run.sh --case 1 --skip-build --device 2
```

The aggregate precision report is written to `results.json`; per-case records
are under `build/cases/case_XX/result.json`. Input/output binary payloads are
deleted after verification to keep the workspace compact.
