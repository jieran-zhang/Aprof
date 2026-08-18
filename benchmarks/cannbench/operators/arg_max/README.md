# arg_max Ascend C direct invocation

Standalone Ascend C implementation of the level2 `arg_max` task. It supports
float16, float32, bfloat16, int32, and int64 input, arbitrary valid axes,
negative axes, `keepdim`, first-index tie breaking, and torch-compatible NaN
selection. Output dtype is always int64.

Build and run all 20 source cases on device 4:

```bash
./run.sh --all --device 4
```

Run one already-built case:

```bash
./run.sh --case 15 --skip-build --device 4
```

Aggregate precision evidence is written to `results.json`; individual records
are under `build/cases/case_*/result.json`. `harness.test_gate` is off. This
flash version intentionally prioritizes exact correctness over optimization.
