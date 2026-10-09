# MaskedScale AscendC direct invocation

Standalone `dav-2201` implementation of `y = x * mask * scale`, including mixed
`x`/`mask` dtypes and tail-safe execution. Build and run all 20 official cases
on a real NPU:

```bash
./run.sh --all --device 0
```

The executable is `build/masked_scale`; per-case precision records are under
`build/cases/case_*/result.json`, with the aggregate in `results.json`.
