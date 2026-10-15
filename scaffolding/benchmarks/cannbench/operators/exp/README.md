# Exp AscendC direct invocation

Standalone `dav-2201` implementation of `exp(x, base, scale, shift)` with FP32
internal compute for FP16/BF16. Build and run all official cases on a real NPU:

```bash
./run.sh --all --device 0
```

The executable is `build/exp`; per-case precision records are under
`build/cases/case_*/result.json`, with the aggregate in `results.json`.
