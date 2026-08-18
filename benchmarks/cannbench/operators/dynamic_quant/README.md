# dynamic_quant Ascend C direct invocation

Standalone per-token dynamic quantization for float16 and bfloat16 input. It
produces int8 values plus float32 per-token dequantization scales, including
the source golden's zero, Inf, and NaN behavior.

Build and run all 20 source cases on device 0:

```bash
./run.sh --all --device 0
```

Run one already-built case:

```bash
./run.sh --case 17 --skip-build --device 0
```

Aggregate evidence is written to `results.json`; individual records are under
`build/cases/case_*/result.json`. `harness.test_gate` is off and this flash
version intentionally skips profiling and optimization.
