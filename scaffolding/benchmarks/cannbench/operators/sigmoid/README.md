# Sigmoid AscendC direct invocation

Standalone `dav-2201` implementation of `sigmoid(x)` for float16, float32, and
bfloat16. FP16/BF16 use FP32 internal calculation. Build and execute all 20
official `cases.csv` cases on a real NPU with:

```bash
./run.sh --all --device 0
```

The executable is `build/sigmoid`. Per-case precision records are written to
`build/cases/case_*/result.json`; the aggregate is `results.json`.
