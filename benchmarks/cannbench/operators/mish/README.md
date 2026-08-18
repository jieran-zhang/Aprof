# Mish direct invocation

Standalone Ascend C direct-invocation implementation of
`y = x * tanh(softplus(x))` for float16, float32, and bfloat16 on
Ascend910 (`dav-2201`).

```bash
./run.sh --all --device 4
```

The runner builds the executable, generates the exact 20 source cases,
runs them on the selected NPU, verifies precision against PyTorch, and writes
`results.json`.
